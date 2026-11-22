# Nenza PCB

Abra `Nenza_PCB.kicad_pro` no KiCad e entre no Editor de Esquemas.

| Sinal | ESP32-C3 SuperMini | Conexão |
| --- | --- | --- |
| SDA | GPIO5 | SDA do OLED e do BMP280 |
| SCL | GPIO6 | SCL do OLED e do BMP280 |
| BTN1 | GPIO0 | Botão anterior para GND |
| BTN2 | GPIO1 | Botão próximo para GND |
| BTN3 | GPIO3 | Botão OK/voltar para GND |
| +3V3 | 3V3 | Alimentação dos periféricos |
| GND | GND | Terra comum |

Alimente pelo USB-C da SuperMini. O barramento I²C opera em 3,3 V a 100 kHz. O OLED SSD1306 está em 0x3C. Para o BMP280 em 0x76, fixe CSB em 3,3 V e SDO em GND quando esses pinos estiverem expostos. Em módulos de quatro pinos, confira o endereço definido de fábrica. R1/R2 de 4,7 kΩ são opcionais e ficam sem montagem se os módulos já fornecerem pull-ups adequados.

Para portar o firmware original, use um único objeto I²C para os dois periféricos, remapeie os botões para GPIO0/1/3 com pull-ups internos e retire a inicialização e a leitura do encoder. Confira o funcionamento do USB serial, do Wi-Fi e do OLED no build MicroPython para ESP32-C3.

O esquema representa módulos completos. Confira a ordem dos pinos, as dimensões dos módulos e dos botões e a área livre da antena na placa física antes de atribuir footprints e rotear. Na biblioteca, U1 numera 1–8 na fileira de 5V a GPIO0 e 9–16 na fileira de GPIO5 a GPIO21, ambas do lado do USB em direção à antena. Essa numeração deve ser reproduzida no footprint.

- [Pinagem da ESP32-C3 SuperMini](https://www.th3dstudio.com/wp-content/uploads/2024/05/ESP32-C3-SuperMini-datasheet.pdf)
- [Guia de hardware ESP32-C3 da Espressif](https://docs.espressif.com/projects/esp-hardware-design-guidelines/en/latest/esp32c3/schematic-checklist.html)
