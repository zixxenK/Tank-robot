/**
 * main.cpp — ESP32-S3 Camera Firmware
 *
 * Initialises the OV2640/OV5640 camera and streams MJPEG over HTTP
 * on the local network for consumption by the Rock64 ROS2 bridge node.
 *
 * Board:  ESP32-S3-DevKitC-1 (CAMERA_MODEL_ESP32S3)
 * Flash:  esp32-camera library (lib_deps in platformio.ini)
 */

#include <Arduino.h>
#include <WiFi.h>
#include "esp_camera.h"
#include "esp_http_server.h"

// ── WiFi credentials ─────────────────────────────────────────────────────
// Set via build_flags or a local secrets.h (not committed).
#ifndef WIFI_SSID
#  define WIFI_SSID "your_ssid"
#endif
#ifndef WIFI_PASS
#  define WIFI_PASS "your_password"
#endif

// ── Camera pin mapping (ESP32-S3 DevKitC-1 with OV2640) ──────────────────
#define PWDN_GPIO_NUM  -1
#define RESET_GPIO_NUM -1
#define XCLK_GPIO_NUM  15
#define SIOD_GPIO_NUM   4
#define SIOC_GPIO_NUM   5
#define Y9_GPIO_NUM    16
#define Y8_GPIO_NUM    17
#define Y7_GPIO_NUM    18
#define Y6_GPIO_NUM    12
#define Y5_GPIO_NUM    10
#define Y4_GPIO_NUM     8
#define Y3_GPIO_NUM     9
#define Y2_GPIO_NUM    11
#define VSYNC_GPIO_NUM  6
#define HREF_GPIO_NUM   7
#define PCLK_GPIO_NUM  13

static httpd_handle_t stream_httpd = nullptr;

// ── MJPEG stream handler ──────────────────────────────────────────────────
static esp_err_t stream_handler(httpd_req_t *req) {
    camera_fb_t *fb = nullptr;
    esp_err_t res = ESP_OK;
    static const char *STREAM_CONTENT_TYPE =
        "multipart/x-mixed-replace;boundary=frame";
    static const char *STREAM_BOUNDARY = "\r\n--frame\r\n";
    static const char *STREAM_PART =
        "Content-Type: image/jpeg\r\nContent-Length: %zu\r\n\r\n";

    res = httpd_resp_set_type(req, STREAM_CONTENT_TYPE);
    if (res != ESP_OK) return res;

    char part_buf[64];
    while (true) {
        fb = esp_camera_fb_get();
        if (!fb) {
            Serial.println("[camera] Frame capture failed");
            res = ESP_FAIL;
            break;
        }

        res = httpd_resp_send_chunk(req, STREAM_BOUNDARY,
                                    strlen(STREAM_BOUNDARY));
        if (res == ESP_OK) {
            size_t hlen = snprintf(part_buf, sizeof(part_buf),
                                   STREAM_PART, fb->len);
            res = httpd_resp_send_chunk(req, part_buf, hlen);
        }
        if (res == ESP_OK) {
            res = httpd_resp_send_chunk(req,
                                        reinterpret_cast<const char *>(fb->buf),
                                        fb->len);
        }

        esp_camera_fb_return(fb);
        if (res != ESP_OK) break;
    }
    return res;
}

// ── Camera initialisation ─────────────────────────────────────────────────
static bool camera_init() {
    camera_config_t config;
    config.ledc_channel = LEDC_CHANNEL_0;
    config.ledc_timer   = LEDC_TIMER_0;
    config.pin_d0       = Y2_GPIO_NUM;
    config.pin_d1       = Y3_GPIO_NUM;
    config.pin_d2       = Y4_GPIO_NUM;
    config.pin_d3       = Y5_GPIO_NUM;
    config.pin_d4       = Y6_GPIO_NUM;
    config.pin_d5       = Y7_GPIO_NUM;
    config.pin_d6       = Y8_GPIO_NUM;
    config.pin_d7       = Y9_GPIO_NUM;
    config.pin_xclk     = XCLK_GPIO_NUM;
    config.pin_pclk     = PCLK_GPIO_NUM;
    config.pin_vsync    = VSYNC_GPIO_NUM;
    config.pin_href     = HREF_GPIO_NUM;
    config.pin_sccb_sda = SIOD_GPIO_NUM;
    config.pin_sccb_scl = SIOC_GPIO_NUM;
    config.pin_pwdn     = PWDN_GPIO_NUM;
    config.pin_reset    = RESET_GPIO_NUM;
    config.xclk_freq_hz = 20000000;
    config.pixel_format = PIXFORMAT_JPEG;
    config.frame_size   = FRAMESIZE_VGA;
    config.jpeg_quality = 12;
    config.fb_count     = psramFound() ? 2 : 1;
    config.grab_mode    = CAMERA_GRAB_WHEN_EMPTY;
    config.fb_location  = psramFound() ? CAMERA_FB_IN_PSRAM
                                       : CAMERA_FB_IN_DRAM;

    esp_err_t err = esp_camera_init(&config);
    if (err != ESP_OK) {
        Serial.printf("[camera] Init failed: 0x%x\n", err);
        return false;
    }
    Serial.println("[camera] Initialised OK");
    return true;
}

// ── MJPEG HTTP server setup ───────────────────────────────────────────────
static void start_stream_server() {
    httpd_config_t config = HTTPD_DEFAULT_CONFIG();
    config.server_port = 81;

    httpd_uri_t stream_uri = {
        .uri      = "/stream",
        .method   = HTTP_GET,
        .handler  = stream_handler,
        .user_ctx = nullptr
    };

    if (httpd_start(&stream_httpd, &config) == ESP_OK) {
        httpd_register_uri_handler(stream_httpd, &stream_uri);
        Serial.printf("[http] Stream server started on port %d\n",
                      config.server_port);
    }
}

// ── Arduino entry points ──────────────────────────────────────────────────
void setup() {
    Serial.begin(115200);
    Serial.println("[boot] ESP32-S3 Camera Node starting...");

    // WiFi initialisation
    WiFi.mode(WIFI_STA);
    WiFi.begin(WIFI_SSID, WIFI_PASS);
    Serial.print("[wifi] Connecting");
    while (WiFi.status() != WL_CONNECTED) {
        delay(500);
        Serial.print(".");
    }
    Serial.printf("\n[wifi] Connected — IP: %s\n",
                  WiFi.localIP().toString().c_str());

    if (!camera_init()) {
        Serial.println("[boot] Camera init failed — halting");
        while (true) delay(1000);
    }

    start_stream_server();
    Serial.println("[boot] Ready. Stream: http://" +
                   WiFi.localIP().toString() + ":81/stream");
}

void loop() {
    delay(10000);
}
