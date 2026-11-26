from machine import Pin
from time import ticks_diff
from config import DEBOUNCE_MS, TOQUE_LONGO_MS


class Botao:
    def __init__(self, gpio):
        self.pin = Pin(gpio, Pin.IN, Pin.PULL_UP)
        self.pressionado = False
        self.inicio_pressao = None
        self.inicio_solto = None

    def gesto(self, agora):
        if self.clicou(agora):
            self.inicio_pressao = agora
        if self.inicio_pressao is None:
            return None
        if not self.pressionado:
            duracao_ms = ticks_diff(self.inicio_solto, self.inicio_pressao)
            self.inicio_pressao = None
            if duracao_ms >= DEBOUNCE_MS:
                return "longo" if duracao_ms >= TOQUE_LONGO_MS else "curto"
        elif self.inicio_solto is None and ticks_diff(agora, self.inicio_pressao) >= TOQUE_LONGO_MS:
            self.inicio_pressao = None
            return "longo"
        return None

    def clicou(self, agora):
        if self.pin.value() == 0:
            self.inicio_solto = None
            novo_clique = not self.pressionado
            self.pressionado = True
            return novo_clique

        if self.pressionado:
            if self.inicio_solto is None:
                self.inicio_solto = agora
            elif ticks_diff(agora, self.inicio_solto) >= DEBOUNCE_MS:
                self.pressionado = False
        return False

def ler_config(nvs, chave, padrao, maximo):
    try:
        valor = nvs.get_i32(chave)
    except OSError:
        return padrao
    return valor if 0 <= valor <= maximo else padrao


def salvar_config(nvs, chave, valor):
    try:
        nvs.set_i32(chave, valor)
        nvs.commit()
    except OSError as erro:
        print("Configuracoes:", erro)


class Encoder:
    # A e B formam um codigo Gray. Mudancas invalidas nao geram passos.
    DELTAS = (0, -1, 1, 0, 1, 0, 0, -1, -1, 0, 0, 1, 0, 1, -1, 0)

    def __init__(self, pinos, transicoes):
        self.a = Pin(pinos[0], Pin.IN, Pin.PULL_UP)
        self.b = Pin(pinos[1], Pin.IN, Pin.PULL_UP)
        self.estado = self.a.value() * 2 + self.b.value()
        self.transicoes = transicoes
        self.contagem = self.lido = self.parcial = 0
        bordas = Pin.IRQ_RISING | Pin.IRQ_FALLING
        self.a.irq(self._mudou, bordas)
        self.b.irq(self._mudou, bordas)

    def _mudou(self, pin):
        estado = self.a.value() * 2 + self.b.value()
        if estado == self.estado:
            return
        delta = self.DELTAS[self.estado * 4 + estado]
        self.estado = estado
        self.parcial = self.parcial + delta if delta else 0
        if self.parcial == self.transicoes:
            self.contagem = (self.contagem + 1) & 0xffff
            self.parcial = 0
        elif self.parcial == -self.transicoes:
            self.contagem = (self.contagem - 1) & 0xffff
            self.parcial = 0

    def ler(self):
        # O callback escreve apenas contagem e o loop escreve apenas lido.
        contagem = self.contagem
        passos = ((contagem - self.lido + 32768) & 0xffff) - 32768
        self.lido = contagem
        return passos
