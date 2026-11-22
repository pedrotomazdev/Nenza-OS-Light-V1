from array import array
from time import ticks_diff

from config import PRESSAO_NIVEL_MAR_HPA

INTERVALO_MS = 10 * 60_000
BLOCOS_24H = 144
CAPACIDADE = BLOCOS_24H + 1  # Inclui o bloco em andamento.
TEMPERATURA = 0
PRESSAO = 1


def altitude_estimada(pressao):
    if pressao is None or pressao <= 0:
        return None
    return 44307.69 * (1 - (pressao / PRESSAO_NIVEL_MAR_HPA) ** 0.190284)


def indicador_experimental(pressao_3h, temperatura_h):
    if pressao_3h is None or temperatura_h is None:
        return "Aguardando 3h"
    if pressao_3h <= -2 and temperatura_h <= -0.5:
        return "Possivel instab."
    if pressao_3h >= 2 and temperatura_h >= 0.5:
        return "Melhora possivel"
    return "Sem sinal claro"


class ResumoClima:
    def __init__(self, agora):
        self.ultimo_tick = agora
        self.resto_ms = 0
        self.bloco = 0
        # Cada grupo guarda soma, minima, maxima e quantidade de leituras.
        self.series = tuple(array("f", [0.0] * (CAPACIDADE * 4)) for _ in range(2))

    def registrar(self, agora, amostra):
        decorrido = self.resto_ms + ticks_diff(agora, self.ultimo_tick)
        self.ultimo_tick = agora
        avancou, self.resto_ms = divmod(decorrido, INTERVALO_MS)
        self.bloco += avancou
        for serie, valor in zip(self.series, amostra):
            for atraso in range(min(avancou, CAPACIDADE)):
                base = ((self.bloco - atraso) % CAPACIDADE) * 4
                serie[base + 3] = 0
            if valor is None:
                continue
            base = (self.bloco % CAPACIDADE) * 4
            quantidade = serie[base + 3]
            if quantidade:
                serie[base] += valor
                serie[base + 1] = min(serie[base + 1], valor)
                serie[base + 2] = max(serie[base + 2], valor)
            else:
                serie[base] = serie[base + 1] = serie[base + 2] = valor
            serie[base + 3] = quantidade + 1

    def variacao(self, metrica, horas):
        recente = self.bloco - 1
        passado = recente - horas * 6
        if passado < 0:
            return None
        serie = self.series[metrica]
        atual = (recente % CAPACIDADE) * 4
        anterior = (passado % CAPACIDADE) * 4
        n_atual = serie[atual + 3]
        n_anterior = serie[anterior + 3]
        if n_atual and n_anterior:
            return serie[atual] / n_atual - serie[anterior] / n_anterior
        return None

    def estatisticas(self, metrica):
        serie = self.series[metrica]
        soma = quantidade = cobertura = 0
        minimo = maximo = None
        for bloco in range(max(0, self.bloco - BLOCOS_24H), self.bloco):
            base = (bloco % CAPACIDADE) * 4
            n = serie[base + 3]
            if n:
                soma += serie[base]
                quantidade += n
                cobertura += 1
                minimo = serie[base + 1] if minimo is None else min(minimo, serie[base + 1])
                maximo = serie[base + 2] if maximo is None else max(maximo, serie[base + 2])
        if quantidade:
            return minimo, maximo, soma / quantidade, cobertura
        return None
