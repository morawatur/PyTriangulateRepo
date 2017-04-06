serName = 'd'
nFiles = 20
dimSize = 1024
# dimSize = 2048
numInFocus = 10
idxInFocus = numInFocus - 1
refIdx = 10
predefDfStep = 2.0e-9
nIterations = 20
pxWidth = 718.243e-12
# pxWidth = 359.122e-12
# pxWidth = 286.515e-12
# pxWidth = 143.258e-12
# pxWidth = 20.5144e-12
# pxWidth = 634.331e-12
# pxWidth = 502.377e-12
# pxWidth = 141.918e-12
# pxWidth = 390.772e-12
# pxWidth = 52.8781e-12
ewfLambda = 1.97e-12
dfStepMin, dfStepMax, dfStepChange = 0.4, 1.2, 0.02
ccWidgetDim = 1024
badPxThreshold = 4.0
# badPxThreshold = 1.1    # seria h1
# badPxThreshold = 2.3    # serie holo+-
gridDim = 3
nDivForUnwarp = 8

inputDir = 'input/'
resultsDir = 'results/'
imgResultsDir = resultsDir + 'img/'
ccfResultsDir = resultsDir + 'ccf/'
focResultsDir = resultsDir + 'foc/'
cropResultsDir = resultsDir + 'crop/'
ccfMaxDir = resultsDir + 'ccfmax/'

ccfName = 'ccf'
focName = 'foc'
cropName = 'crop'
ccfMaxName = 'ccfmax'