from numba import cuda
import GUI_Holo as gui

cuda.select_device(0)
dev = cuda.get_current_device()
print('CUDA device in use: ' + dev.name.decode())

# Potrzebne jeszcze:
# - funkcje polar i rect z cmath dzialaja zle na GPU, jezeli faza przekracza 2pi
# - holo z referencja
# - kontrola jasnosci, gammy i kontrastu

gui.RunTriangulationWindow()