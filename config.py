DEBOUNCE_MS = 30
INATIVIDADE_MS = 60_000
QUADRO_MS = 50
FAIXA_AMARELA_PX = 16
ATUALIZACAO_MS = 15_000
AMOSTRAS = 60
PRESSAO_NIVEL_MAR_HPA = 1013.25
POMODORO_MS = 25 * 60_000
TOQUE_LONGO_MS = 650
GRAFICOS_REDE = (("PING", " ms"), ("CPU", " C"), ("RAM", "%"))
GRAFICOS = GRAFICOS_REDE + (("TEMP AMB", " C"), ("PRESS", " hPa"))
TITULOS = ("NENZAHUB", "CPU", "MEMORIA", "REDE", "BATERIA", "DISCO")
ANIMACOES = (
    "Gatinho", "Nenza DVD", "VU USB", "Espectro USB", "Onda USB",
    "Particulas", "Estrelas", "Ondas", "Geometria", "Olhos", "Logo",
)
BANDAS_ESPECTRO = 12
PONTOS_ONDA = 64
QUADRO_ESPECTRO_MS = 40
DIAGNOSTICO_MEMORIA = False
# Controles do checkout local; use None para manter entradas extras desativadas.
GPIO_BOTOES = (25, 26)
GPIO_CONFIRMAR = None
GPIO_ENCODER = None  # Exemplo: (4, 15), se livres na sua placa.
TRANSICOES_ENCODER = 2
