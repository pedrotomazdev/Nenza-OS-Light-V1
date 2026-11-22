from machine import Pin
from time import ticks_diff
from config import DEBOUNCE_MS, DIAGNOSTICO_ENCODER, TOQUE_LONGO_MS


class EncoderRotativo:
    TRANSICOES_POR_PASSO = 2
    # Linhas: estado anterior. Colunas: estado atual (A << 1 | B).
    TRANSICOES = (
        (0, 1, -1, 0),
        (-1, 0, 0, 1),
        (1, 0, 0, -1),
        (0, -1, 1, 0),
    )

    def __init__(self, gpio_a, gpio_b):
        self.a = Pin(gpio_a, Pin.IN, Pin.PULL_UP)
        self.b = Pin(gpio_b, Pin.IN, Pin.PULL_UP)
        self.anterior = (self.a.value() << 1) | self.b.value()
        self.parcial = 0
        self.posicao = 0
        self.ultima_posicao = 0
        self.validas = 0
        self.invalidas = 0
        self.ultimo_log = None
        self.estado_log = None

    def atualizar(self):
        atual = (self.a.value() << 1) | self.b.value()
        if atual == self.anterior:
            return
        passo = self.TRANSICOES[self.anterior][atual]
        self.anterior = atual
        if not passo:
            if DIAGNOSTICO_ENCODER:
                self.invalidas += 1
            self.parcial = 0
            return
        if DIAGNOSTICO_ENCODER:
            self.validas += 1
        self.parcial += passo
        if abs(self.parcial) == self.TRANSICOES_POR_PASSO:
            self.posicao += passo
            self.parcial = 0

    def ler_passos(self):
        posicao = self.posicao
        passos = posicao - self.ultima_posicao
        self.ultima_posicao = posicao
        return passos

    def mostrar_diagnostico(self, agora):
        if self.ultimo_log is not None and ticks_diff(agora, self.ultimo_log) < 200:
            return
        self.ultimo_log = agora
        estado = (self.a.value(), self.b.value(), self.validas, self.invalidas,
                  self.parcial, self.posicao)
        if estado != self.estado_log:
            self.estado_log = estado
            print("[ENCODER] A={} B={} validas={} invalidas={} parcial={} posicao={}".format(*estado))


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
