from machine import I2C, Pin
from struct import unpack
from time import ticks_add, ticks_diff

from config import AMOSTRAS
from clima import ResumoClima


class BMP280:
    def __init__(self, i2c, endereco=0x76):
        self.i2c = i2c
        self.endereco = endereco
        if i2c.readfrom_mem(endereco, 0xD0, 1)[0] != 0x58:
            raise ValueError("Sensor nao identificado como BMP280")
        self.calibracao = unpack("<HhhHhhhhhhhh", i2c.readfrom_mem(endereco, 0x88, 24))
        i2c.writeto_mem(endereco, 0xF4, b"\x27")

    def medir(self):
        dados = self.i2c.readfrom_mem(self.endereco, 0xF7, 6)
        adc_p = (dados[0] << 12) | (dados[1] << 4) | (dados[2] >> 4)
        adc_t = (dados[3] << 12) | (dados[4] << 4) | (dados[5] >> 4)
        if adc_t == 0x80000:
            return None, None

        t1, t2, t3, p1, p2, p3, p4, p5, p6, p7, p8, p9 = self.calibracao
        v1 = (adc_t / 16384.0 - t1 / 1024.0) * t2
        v2 = ((adc_t / 131072.0 - t1 / 8192.0) ** 2) * t3
        t_fine = v1 + v2
        temperatura = t_fine / 5120.0

        v1 = t_fine / 2.0 - 64000.0
        v2 = v1 * v1 * p6 / 32768.0
        v2 += v1 * p5 * 2.0
        v2 = v2 / 4.0 + p4 * 65536.0
        v1 = (p3 * v1 * v1 / 524288.0 + p2 * v1) / 524288.0
        v1 = (1.0 + v1 / 32768.0) * p1
        if v1 == 0 or adc_p == 0x80000:
            return temperatura, None

        p = (1048576.0 - adc_p - v2 / 4096.0) * 6250.0 / v1
        v1 = p9 * p * p / 2147483648.0
        v2 = p * p8 / 32768.0
        return temperatura, (p + (v1 + v2 + p7) / 16.0) / 100.0


class HistoricoBMP280:
    def __init__(self, agora):
        self.i2c = None
        self.sensor = None
        self.proxima_leitura = agora
        self.atual = (None, None)
        self.revisao = 0
        self.historico = [None] * AMOSTRAS
        self.resumo = ResumoClima(agora)

    def atualizar(self, agora):
        if ticks_diff(agora, self.proxima_leitura) < 0:
            return
        self.proxima_leitura = ticks_add(agora, 1000)
        try:
            if self.i2c is None:
                self.i2c = I2C(0, scl=Pin(22), sda=Pin(21), freq=100_000, timeout=10_000)
            if self.sensor is None:
                self.sensor = BMP280(self.i2c)
                # Aguarda a primeira conversao sem pausar o loop da interface.
            else:
                self.atual = self.sensor.medir()
        except (OSError, ValueError):
            self.sensor = None
            self.atual = (None, None)
        self.historico[self.revisao % AMOSTRAS] = self.atual
        self.revisao += 1
        self.resumo.registrar(agora, self.atual)

    def copiar_metrica(self, metrica, destino):
        quantidade = min(self.revisao, AMOSTRAS)
        primeiro = self.revisao - quantidade
        for indice in range(quantidade):
            destino[indice] = self.historico[(primeiro + indice) % AMOSTRAS][metrica]
        return self.revisao, quantidade
