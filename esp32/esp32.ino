#include <Arduino.h>
#include "driver/spi_slave.h"
#include "esp_wifi.h"
#include "esp_event.h"
#include "esp_log.h"
#include "nvs_flash.h"
#include <WiFi.h>

#define WIFI_SSID "esp_ap"
#define WIFI_PASS "esp32pass"
#define MAX_STA_CONN 1
#define TCP_PORT 8080

#define PIN_MOSI 13
#define PIN_MISO 11
#define PIN_SCLK 12
#define PIN_CS   10

#define OFFSET_PLUS 17
#define OFFSET_MINUS 18

#define VGA_0 34
#define VGA_1 35

#define ADC_CLK_EN 38
#define ADC_OTR 39
#define ADC_POWER_DOWN 40
#define ADC_MSB 41

#define NUM_POINTS 1000                      // Number of uint16_t values expected
#define FRAME_SIZE_BYTES (NUM_POINTS * 2) // Size of SPI frame in bytes

#define PASSWORD_CODE 0xDEADBEEF

// DAC constants for voltage offset
#define DAC_PLUS_PIN 17
#define DAC_MINUS_PIN 18
#define DAC_STEP_VOLTAGE 0.01289f  // 3.3V / 256 = ~12.89mV per step
#define MAX_OFFSET_VOLTAGE 1.0f    // Maximum offset is 1V
#define MAX_DAC_VALUE 78           // 1V / 0.01289V ≈ 78 steps

uint8_t * rx_buf;
uint8_t * tx_buf; 

// TCP server
WiFiServer server(TCP_PORT);
WiFiClient client;

void set_voltage_offset(uint32_t encoded_value) {

  int32_t offset = (int32_t)encoded_value - 78;
  
  if (offset > 0) {
    // Positive offset: use DAC+ only, DAC- = 0
    uint8_t dac_value = (offset > MAX_DAC_VALUE) ? MAX_DAC_VALUE : (uint8_t)offset;
    dacWrite(DAC_PLUS_PIN, 225);
    dacWrite(DAC_MINUS_PIN, 225 - offset);
    Serial.printf("Offset: +%d DAC steps (DAC+ = %d, DAC- = 0)\n", offset, dac_value);
  } else if (offset < 0) {
    // Negative offset: use DAC- only, DAC+ = 0
    uint8_t dac_value = (-offset > MAX_DAC_VALUE) ? MAX_DAC_VALUE : (uint8_t)(-offset);
    dacWrite(DAC_PLUS_PIN, 225 + offset);
    dacWrite(DAC_MINUS_PIN, 225);
    Serial.printf("Offset: %d DAC steps (DAC+ = 0, DAC- = %d)\n", offset, dac_value);
  } else {
    // Zero offset: both DACs = 0
    dacWrite(DAC_PLUS_PIN, 225);
    dacWrite(DAC_MINUS_PIN, 225);
    Serial.println("Offset: 0 (both DACs = 0)");
  }
}

void check_client_data() {
  // Non-blocking check for incoming data from client
  if (client && client.connected() && client.available() >= 6) {
    // Read exactly 6 bytes into the tx_buffer
    uint8_t temp_buffer[6];
    int bytes_read = 0;
    
    for (int i = 0; i < 6 && client.available(); i++) {
      temp_buffer[i] = client.read();
      bytes_read++;
    }
    
    if (bytes_read == 6) {
      // Parse the command
      uint16_t op_code = temp_buffer[0] | (temp_buffer[1] << 8);  // Little-endian
      uint32_t value = temp_buffer[2] | (temp_buffer[3] << 8) | 
                       (temp_buffer[4] << 16) | (temp_buffer[5] << 24);
      
      Serial.printf("Command received - OpCode: %u, Value: %lu\n", op_code, value);
      
      // Handle offset command (op_code 3) locally on ESP32
      if (op_code == 3) {
        set_voltage_offset(value);
        // Don't forward offset commands to STM32
        memset(tx_buf, 0, FRAME_SIZE_BYTES);
      } else {
        // Forward other commands to STM32 via SPI
        memset(tx_buf, 0, FRAME_SIZE_BYTES);
        tx_buf[0] = PASSWORD_CODE >> 24;
        tx_buf[1] = (PASSWORD_CODE >> 16) & 0xFF;
        tx_buf[2] = (PASSWORD_CODE >> 8) & 0xFF;
        tx_buf[3] = PASSWORD_CODE & 0xFF;
        
        // Copy to tx_buffer
        memcpy(tx_buf + 4, temp_buffer, 6);
      }
    } else {
      Serial.printf("Warning: Only read %d bytes instead of 6\n", bytes_read);
    }
  } else {
    memset(tx_buf, 0, FRAME_SIZE_BYTES);
  }
}

void setup_wifi() {
  WiFi.mode(WIFI_AP);
  WiFi.softAP(WIFI_SSID, WIFI_PASS);
  Serial.print("AP IP: ");
  Serial.println(WiFi.softAPIP());
  server.begin();
  Serial.println("TCP server started on port 8080");
}

void setup_spi_slave() {
  spi_bus_config_t buscfg = {
    .mosi_io_num = PIN_MOSI,
    .miso_io_num = PIN_MISO,
    .sclk_io_num = PIN_SCLK,
    .quadwp_io_num = -1,
    .quadhd_io_num = -1,
    .max_transfer_sz = 2*FRAME_SIZE_BYTES
  };

  spi_slave_interface_config_t slvcfg = {
    .spics_io_num = PIN_CS,
    .flags = 0,
    .queue_size = 1,
    .mode = 0,  // SPI mode 0
    .post_setup_cb = nullptr,
    .post_trans_cb = nullptr
  };

  esp_err_t ret = spi_slave_initialize(SPI2_HOST, &buscfg, &slvcfg, SPI_DMA_CH_AUTO);
  if (ret != ESP_OK) {
    Serial.println("SPI slave init failed!");
  } else {
    Serial.println("SPI slave initialized.");
  }
}

void setup() {
  Serial.begin(115200);

  while (!Serial) {
    delay(100);
  }
  delay(1000);
  
  Serial.println("\n--- ESP32 Serial Connected ---");

   // Allocate DMA-capable buffers
  rx_buf = (uint8_t*)heap_caps_malloc(FRAME_SIZE_BYTES, MALLOC_CAP_DMA);
  tx_buf = (uint8_t*)heap_caps_malloc(FRAME_SIZE_BYTES, MALLOC_CAP_DMA);

  if (!rx_buf || !tx_buf) {
    Serial.println("DMA buffer allocation failed!");
    while (1);  // halt
  }

  memset(rx_buf, 0, FRAME_SIZE_BYTES);
  memset(tx_buf, 0, FRAME_SIZE_BYTES);

  pinMode(ADC_CLK_EN, OUTPUT);
  digitalWrite(ADC_CLK_EN, HIGH);

  // Initialize DAC outputs for voltage offset (start at 0)
  dacWrite(DAC_PLUS_PIN, 225);
  dacWrite(DAC_MINUS_PIN, 225);

  setup_wifi();
  setup_spi_slave();
}

bool client_was_connected = false;

void loop() {
  // Handle client connection state changes
  bool currently_connected = client && client.connected();
  
  // Detect disconnect and clean up
  if (!currently_connected && client_was_connected) {
    Serial.println("Client disconnected");
    client.stop();  // Properly close the socket
    client_was_connected = false;
  }
  
  if (!currently_connected) {
    // Check for new client only if not connected
    WiFiClient newClient = server.available();
    if (newClient) {
      // New client connected
      client = newClient;
      client_was_connected = true;
      Serial.println("Client connected");
      Serial.print("Client IP: ");
      Serial.println(client.remoteIP());
    } else {
      // No client, wait a bit
      delay(100);
      return;
    }
  }

  // Check for incoming data from client (non-blocking) - do this before SPI
  check_client_data();

  // Perform SPI transaction
  spi_slave_transaction_t t;
  memset(&t, 0, sizeof(t));
  t.length = FRAME_SIZE_BYTES * 8;  // bits
  t.tx_buffer = tx_buf;
  t.rx_buffer = rx_buf;

  esp_err_t ret = spi_slave_transmit(SPI2_HOST, &t, portMAX_DELAY);

  if (ret == ESP_OK) {
    if (client && client.connected()) {   
      size_t bytes_written = client.write(rx_buf, FRAME_SIZE_BYTES);
      if (bytes_written != FRAME_SIZE_BYTES) {
        // Write failed - client likely disconnected mid-transfer
        Serial.println("Write failed - closing connection");
        client.stop();
        client_was_connected = false;
      }
    }
  }
}
