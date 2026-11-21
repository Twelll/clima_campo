# Esquemas de ligação da estação meteorológica

## 1. ESP32 → NRF24L01 com antena

O ESP32 recebe as medições pelo NRF24L01 e as encaminha ao servidor por Wi-Fi.

| Pino do NRF24L01 | Ligação |
|---|---|
| VCC | Alimentação regulada de **3,3 V** |
| GND | GND do ESP32 e da fonte do rádio |
| CE | GPIO **4** |
| CSN / CS | GPIO **5** |
| SCK | GPIO **18** |
| MOSI | GPIO **23** |
| MISO | GPIO **19** |
| IRQ | Não conectado |

```text
ESP32                       NRF24L01
GPIO 4  ─────────────────── CE
GPIO 5  ─────────────────── CSN
GPIO 18 ─────────────────── SCK
GPIO 23 ─────────────────── MOSI
GPIO 19 ─────────────────── MISO
GND     ─────────────────── GND
                               │
Fonte regulada 3,3 V ─────── VCC
GND da fonte ─────────────── GND
```

## 2. Arduino Uno → NRF24L01 com antena

O Arduino coleta as medições e transmite os dados ao ESP32.

| Pino do NRF24L01 | Ligação |
|---|---|
| VCC | Alimentação regulada de **3,3 V** |
| GND | GND do Arduino e da fonte do rádio |
| CE | Digital **9** |
| CSN / CS | Digital **10** |
| SCK | Digital **13** |
| MOSI | Digital **11** |
| MISO | Digital **12** |
| IRQ | Não conectado |

```text
Arduino Uno                 NRF24L01
D9  ─────────────────────── CE
D10 ─────────────────────── CSN
D13 ─────────────────────── SCK
D11 ─────────────────────── MOSI
D12 ─────────────────────── MISO
GND ─────────────────────── GND
                               │
Fonte regulada 3,3 V ─────── VCC
GND da fonte ─────────────── GND
```

### Alimentação dos rádios

- **Não conecte 5 V diretamente ao VCC do NRF24L01.**
- Para os módulos **PA+LNA com antena externa**, utilize alimentação de 3,3 V estável e com corrente suficiente. Prefira um regulador dedicado.
- Se utilizar uma placa adaptadora com regulador, confira a tensão permitida na **entrada do adaptador**.
- Coloque um capacitor de **10 µF a 47 µF** entre VCC e GND, próximo de cada rádio. Em capacitor eletrolítico, positivo no VCC e negativo no GND.
- Instale a antena antes de alimentar e transmitir.
- Cada conjunto deve compartilhar seu próprio GND: Arduino, sensores e rádio de um lado; ESP32 e rádio do outro. **Não é necessário um fio de GND entre as duas estações.**

## 3. Arduino Uno → AHT20 e BMP280

Os dois sensores utilizam o barramento **I²C**, compartilhando SDA e SCL.

| Sinal | Arduino Uno | AHT20 | BMP280 |
|---|---|---|---|
| SDA | **A4 / SDA** | SDA | SDA / SDI |
| SCL | **A5 / SCL** | SCL | SCL / SCK |
| GND | **GND** | GND | GND |

```text
Arduino Uno                AHT20       BMP280
A4 / SDA ────────────────── SDA ─────── SDA
A5 / SCL ────────────────── SCL ─────── SCL
GND      ────────────────── GND ─────── GND
```

**Alimentação e níveis lógicos:** dependem da placa do sensor. O Uno trabalha com sinais de 5 V. Se o módulo não tiver compatibilidade explícita com 5 V, use alimentação compatível com o sensor e um **conversor bidirecional de nível lógico para I²C** entre o Uno e os sensores. Não presuma que todo módulo BMP280 aceita 5 V.

Se AHT20 e BMP280 estiverem em **uma única placa**, conecte apenas uma vez seus terminais SDA, SCL, GND e alimentação.

Se o BMP280 separado tiver os pinos adicionais:

| Pino do BMP280 | Ligação para I²C |
|---|---|
| CS / CSB | VDDIO, normalmente **3,3 V**, conforme o módulo |
| SDO | GND para endereço **0x76**, ou VDDIO para **0x77** |

O código atual procura o BMP280 nos dois endereços.

## 4. Fluxo completo

```text
AHT20 + BMP280
      │ I²C
      ▼
 Arduino Uno
      │ SPI
      ▼
 NRF24L01 TX
      ))) Comunicação sem fio (((
                          NRF24L01 RX
                               │ SPI
                               ▼
                             ESP32
                               │ Wi-Fi
                               ▼
                  Servidor Ubuntu / Pop!_OS
                               │
                               ▼
                      Banco + painel web
```