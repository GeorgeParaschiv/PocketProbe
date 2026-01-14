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
#define PIN_MISO 12
#define PIN_SCLK 14
#define PIN_CS   15

#define NUM_POINTS 1000                      // Number of uint16_t values expected
#define FRAME_SIZE_BYTES (NUM_POINTS * 2) // Size of SPI frame in bytes

uint8_t * rx_buf;
uint8_t * tx_buf; 

// TCP server
WiFiServer server(TCP_PORT);
WiFiClient client;

void check_client_data() {
  // Non-blocking check for incoming data from client
  if (client && client.connected() && client.available() >= 6) {
    // Read exactly 5 bytes into the tx_buffer
    uint8_t temp_buffer[6];
    int bytes_read = 0;
    
    for (int i = 0; i < 6 && client.available(); i++) {
      temp_buffer[i] = client.read();
      bytes_read++;
    }
    
    if (bytes_read == 6) {
      // Copy to tx_buffer
      memcpy(tx_buf, temp_buffer, 6);
      
      Serial.println("Received 6-byte packet from client:");
      for (int i = 0; i < 6; i++) {
        Serial.printf("%02X ", tx_buf[i]);
      }
      Serial.println("\nPacket loaded into tx_buffer for STM32");
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

  esp_err_t ret = spi_slave_initialize(HSPI_HOST, &buscfg, &slvcfg, 1);
  if (ret != ESP_OK) {
    Serial.println("SPI slave init failed!");
  } else {
    Serial.println("SPI slave initialized.");
  }
}

void setup() {
  Serial.begin(115200);
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

  setup_wifi();
  setup_spi_slave();
}

void loop() {
  // Check for new client
  if (!client || !client.connected()) {
    client = server.available();
    if (client) {
      Serial.println("Client connected");
    }
  }

  // Check for incoming data from client (non-blocking) - do this before SPI
  check_client_data();

  // Only receive SPI data if client is connected
  if (client && client.connected()) {
    spi_slave_transaction_t t;
    memset(&t, 0, sizeof(t));
    t.length = FRAME_SIZE_BYTES * 8;  // bits
    t.tx_buffer = tx_buf;
    t.rx_buffer = rx_buf;

    Serial.printf("Preparing to receive %d bytes\n", FRAME_SIZE_BYTES);

    esp_err_t ret = spi_slave_transmit(HSPI_HOST, &t, portMAX_DELAY);

    if (ret == ESP_OK) {
      Serial.println("Received frame:");

      for (int i = 0; i < 10; ++i) {
          printf("%02X %02X\n", rx_buf[2 * i], rx_buf[2 * i + 1]);
      }

      Serial.println("--- End of Frame ---\n");
      
      // Send frame to client
      client.write(rx_buf, FRAME_SIZE_BYTES);
      Serial.println("Frame sent to client");
    }
  } else {
    // No client connected, just wait a bit
    delay(100);
  }
}
