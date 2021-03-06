import math
import re
import sys
from os import path
from functools import partial
import numpy as np
from PyQt4 import QtGui, QtCore
import Dm3Reader3 as dm3
import Constants as const
import ImageSupport as imsup
import CrossCorr as cc
import Transform as tr

# --------------------------------------------------------

class Triangle:
    pass

# --------------------------------------------------------

class TriangulateWidget(QtGui.QWidget):
    def __init__(self):
        super(TriangulateWidget, self).__init__()
        self.display = QtGui.QLabel()
        imagePath = QtGui.QFileDialog.getOpenFileName()
        self.image = LoadImageSeriesFromFirstFile(imagePath)
        self.pointSets = []
        self.createPixmap()
        self.initUI()

    def initUI(self):
        prevButton = QtGui.QPushButton(QtGui.QIcon('gui/prev.png'), '', self)
        prevButton.clicked.connect(partial(self.changePixmap, False))
        nextButton = QtGui.QPushButton(QtGui.QIcon('gui/next.png'), '', self)
        nextButton.clicked.connect(partial(self.changePixmap, True))
        doneButton = QtGui.QPushButton('Done', self)
        doneButton.clicked.connect(self.triangulateAdvanced)

        hbox_nav = QtGui.QHBoxLayout()
        hbox_nav.addWidget(prevButton)
        hbox_nav.addWidget(nextButton)
        hbox_nav.addWidget(doneButton)

        vbox = QtGui.QVBoxLayout()
        vbox.addWidget(self.display)
        vbox.addLayout(hbox_nav)
        self.setLayout(vbox)

        # self.statusBar().showMessage('Ready')
        self.move(250, 30)
        self.setWindowTitle('Triangulation window')
        self.setWindowIcon(QtGui.QIcon('gui/world.png'))
        self.show()
        self.setFixedSize(self.width(), self.height())  # disable window resizing

    def createPixmap(self):
        qImg = QtGui.QImage(imsup.ScaleImage(self.image.buffer, 0.0, 255.0).astype(np.uint8),
                            self.image.width, self.image.height, QtGui.QImage.Format_Indexed8)
        pixmap = QtGui.QPixmap(qImg)
        pixmap = pixmap.scaledToWidth(const.ccWidgetDim)    # !!!
        self.display.setPixmap(pixmap)

    def changePixmap(self, toNext=True):
        newImage = self.image.next if toNext else self.image.prev
        labToDel = self.display.children()
        for child in labToDel:
            child.deleteLater()
            # child.hide()
        if newImage is not None:
            newImage.ReIm2AmPh()
            self.image = newImage
            self.createPixmap()
            if len(self.pointSets) < self.image.numInSeries:
                return
            for pt, idx in zip(self.pointSets[self.image.numInSeries-1], range(1, len(self.pointSets[self.image.numInSeries-1])+1)):
                lab = QtGui.QLabel('{0}'.format(idx), self.display)
                lab.setStyleSheet('font-size:18pt; background-color:white; border:1px solid rgb(0, 0, 0);')
                lab.move(pt[1], pt[0] + lab.height() // 2)
                lab.show()

    # def mousePressEvent(self, QMouseEvent):
    #     print(QMouseEvent.pos())

    def mouseReleaseEvent(self, QMouseEvent):
        pos = QMouseEvent.pos()
        currPos = [pos.x(), pos.y()]
        startPos = ((self.width() - const.ccWidgetDim) // 2, (self.height() - const.ccWidgetDim) // 2)
        endPos = (startPos[0] + const.ccWidgetDim, startPos[1] + const.ccWidgetDim)
        # startPos = ((self.height() - self.image.height) // 2, (self.width() - self.image.width) // 2)
        # endPos = (startPos[0] + self.image.height, startPos[1] + self.image.width)

        if startPos[0] < currPos[0] < endPos[0] and startPos[1] < currPos[1] < endPos[1]:
            currPos = [ a - b for a, b in zip(currPos, startPos) ]
            currDispCoords = [ c - const.ccWidgetDim // 2 for c in currPos ]
            if len(self.pointSets) < self.image.numInSeries:
                self.pointSets.append([])
            self.pointSets[self.image.numInSeries-1].append(currDispCoords)
            lab = QtGui.QLabel('{0}'.format(len(self.pointSets[self.image.numInSeries-1])), self.display)
            lab.setStyleSheet('font-size:18pt; background-color:white; border:1px solid rgb(0, 0, 0);')
            lab.move(currPos[0], currPos[1] + lab.height() // 2)
            lab.show()
            currRealCoords = CalcRealCoords(const.dimSize, currDispCoords)
            print(currRealCoords)

        print(self.pointSets)

    def triangulateBasic(self):
        triangles = [ [ CalcRealCoords(const.dimSize, self.pointSets[trIdx][pIdx]) for pIdx in range(3) ] for trIdx in range(2) ]
        tr1Dists = [ CalcDistance(triangles[0][pIdx1], triangles[0][pIdx2]) for pIdx1, pIdx2 in zip([0, 0, 1], [1, 2, 2]) ]
        tr2Dists = [ CalcDistance(triangles[1][pIdx1], triangles[1][pIdx2]) for pIdx1, pIdx2 in zip([0, 0, 1], [1, 2, 2]) ]

        mags = [dist1 / dist2 for dist1, dist2 in zip(tr1Dists, tr2Dists)]

        rotAngles = []
        for idx, p1, p2 in zip(range(3), triangles[0], triangles[1]):
            rotAngles.append(CalcRotAngle(p1, p2))

        magAvg = np.average(mags)
        rotAngleAvg = np.average(rotAngles)

        img1 = imsup.CopyImage(self.image.prev)
        img2 = imsup.CopyImage(self.image)

        # magnification
        # img2Mag = tr.RescaleImageSki2(img2, magAvg)

        # rotation
        print('rotAngles = {0}'.format(rotAngles))
        print('rotAngleAvg = {0}'.format(rotAngleAvg))
        img2Rot = tr.RotateImageSki2(img2, rotAngleAvg, cut=False)
        img2RotCut = tr.RotateImageSki2(img2, rotAngleAvg, cut=True)
        cropCoords = imsup.DetermineCropCoordsForNewWidth(img1.width, img2RotCut.width)
        img1Crop = imsup.CropImageROICoords(img1, cropCoords)

        # x-y alignment (shift)
        imgs1H = imsup.LinkTwoImagesSmoothlyH(img1Crop, img1Crop)
        linkedImages1 = imsup.LinkTwoImagesSmoothlyV(imgs1H, imgs1H)
        imgs2H = imsup.LinkTwoImagesSmoothlyH(img2RotCut, img2RotCut)
        linkedImages2 = imsup.LinkTwoImagesSmoothlyV(imgs2H, imgs2H)

        img1Alg, img2Alg = cc.AlignTwoImages(linkedImages1, linkedImages2, [0, 1, 2])

        newSquareCoords = imsup.MakeSquareCoords(imsup.DetermineCropCoords(img1Crop.width, img1Crop.height, img2Alg.shift))
        newSquareCoords[2:4] = list(np.array(newSquareCoords[2:4]) - np.array(newSquareCoords[:2]))
        newSquareCoords[:2] = [0, 0]

        img1Res = imsup.CropImageROICoords(img1Alg, newSquareCoords)
        img2Res = imsup.CropImageROICoords(img2Alg, newSquareCoords)

        # ---
        img2RotShift = cc.ShiftImage(img2Rot, img2Alg.shift)
        newSquareCoords2 = imsup.MakeSquareCoords(imsup.DetermineCropCoords(img2RotShift.width, img2RotShift.height, img2Alg.shift))
        img1Crop2 = imsup.CropImageROICoords(img1, newSquareCoords2)
        img2RotCrop = imsup.CropImageROICoords(img2RotShift, newSquareCoords2)

        imsup.SaveAmpImage(img1Crop2, 'holo1.png')
        imsup.SaveAmpImage(img2RotCrop, 'holo2.png')
        # ---

        imsup.SaveAmpImage(img1Alg, 'holo1_big.png')
        imsup.SaveAmpImage(img2Alg, 'holo2_big.png')

        imsup.SaveAmpImage(img1Res, 'holo1_cut.png')
        imsup.SaveAmpImage(img2Res, 'holo2_cut.png')

    def triangulateAdvanced(self):
        triangles = [ [ CalcRealCoords(const.dimSize, self.pointSets[trIdx][pIdx]) for pIdx in range(3) ] for trIdx in range(2) ]
        # tr1 = [ CalcRealCoords(const.dimSize, self.pointSets[0][pIdx]) for pIdx in range(3) ]
        # tr2 = [ CalcRealCoords(const.dimSize, self.pointSets[1][pIdx]) for pIdx in range(3) ]
        # tr1 = self.pointSets[0][:3]
        # tr2 = self.pointSets[1][:3]

        tr1Dists = [ CalcDistance(triangles[0][pIdx1], triangles[0][pIdx2]) for pIdx1, pIdx2 in zip([0, 0, 1], [1, 2, 2]) ]
        tr2Dists = [ CalcDistance(triangles[1][pIdx1], triangles[1][pIdx2]) for pIdx1, pIdx2 in zip([0, 0, 1], [1, 2, 2]) ]

        # zrobic prostsza wersje oparta na zalozeniu ze rotCenter = [0, 0]
        # i bardziej zaawansowana, ktora bierze pod uwage inne polozenie srodka obrotu (rotCenter != [0, 0])
        # w tym drugim przypadku potrzebne jest obliczenie shiftow
        # mozna wyznaczyc dokladniej (sredni) rotCenter (na podstawie trzech a nie dwoch punktow)
        rcSum = [0, 0]
        rotCenters = []
        for idx1 in range(3):
            for idx2 in range(idx1+1, 3):
                print(idx1, idx2)
                rotCenter = tr.FindRotationCenter([triangles[0][idx1], triangles[0][idx2]],
                                                  [triangles[1][idx1], triangles[1][idx2]])
                rotCenters.append(rotCenter)
                print('rotCenter = {0}'.format(rotCenter))
                rcSum = list(np.array(rcSum) + np.array(rotCenter))

        rotCenterAvg = list(np.array(rcSum) / 3.0)
        rcShift = []
        rcShift[:] = rotCenters[0][:]
        rcShift.reverse()
        print('rotCenterAvg = {0}'.format(rotCenterAvg))

        # shift(-rotCenter) obu obrazow
        rcShift = [ -int(rc) for rc in rcShift ]
        print('rcShift = {0}'.format(rcShift))
        img1 = imsup.CopyImage(self.image.prev)
        img2 = imsup.CopyImage(self.image)
        imsup.SaveAmpImage(img1, 'img1.png')
        imsup.SaveAmpImage(img2, 'img2.png')
        img1Rc = cc.ShiftImage(img1, rcShift)
        img2Rc = cc.ShiftImage(img2, rcShift)
        cropCoords = imsup.MakeSquareCoords(imsup.DetermineCropCoords(img1Rc.width, img1Rc.height, rcShift))
        img1Rc = imsup.CropImageROICoords(img1Rc, cropCoords)
        img2Rc = imsup.CropImageROICoords(img2Rc, cropCoords)
        imsup.SaveAmpImage(img1Rc, 'holo1.png')
        imsup.SaveAmpImage(img2Rc, 'img2rc.png')

        rotAngles = []
        for idx, p1, p2 in zip(range(3), triangles[0], triangles[1]):
            p1New = CalcNewCoords(p1, rotCenters[0])
            p2New = CalcNewCoords(p2, rotCenters[0])
            triangles[0][idx] = p1New
            triangles[1][idx] = p2New
            rotAngles.append(CalcRotAngle(p1New, p2New))

        rotAngleAvg = np.average(rotAngles)

        mags = [ dist1 / dist2 for dist1, dist2 in zip(tr1Dists, tr2Dists) ]
        magAvg = np.average(mags)

        tr1InnerAngles = [ CalcInnerAngle(a, b, c) for a, b, c in zip(tr1Dists, tr1Dists[-1:] + tr1Dists[:-1], tr1Dists[-2:] + tr1Dists[:-2]) ]
        tr2InnerAngles = [ CalcInnerAngle(a, b, c) for a, b, c in zip(tr2Dists, tr2Dists[-1:] + tr2Dists[:-1], tr2Dists[-2:] + tr2Dists[:-2]) ]

        triangles[1] = [ tr.RotatePoint(p, ang) for p, ang in zip(triangles[1], rotAngles) ]
        shifts = [ list(np.array(p1) - np.array(p2)) for p1, p2 in zip(triangles[0], triangles[1]) ]
        shiftAvg = [ np.average([sh[0] for sh in shifts]), np.average([sh[1] for sh in shifts]) ]
        shiftAvg = [ int(round(sh)) for sh in shiftAvg ]

        print('---- Triangle 1 ----')
        print([ 'R{0} = {1:.2f} px\n'.format(idx + 1, dist) for idx, dist in zip(range(3), tr1Dists) ])
        print([ 'alpha{0} = {1:.0f} deg\n'.format(idx + 1, angle) for idx, angle in zip(range(3), tr1InnerAngles) ])
        # print('R12 = {0:.2f} px\nR13 = {1:.2f} px\nR23 = {2:.2f} px\n---'.format(r12, r13, r23))
        # print('a1 = {0:.0f} deg\na2 = {1:.0f} deg\na3 = {2:.0f} deg\n---'.format(alpha1, alpha2, alpha3))
        print('---- Triangle 2 ----')
        print([ 'R{0} = {1:.2f} px\n'.format(idx + 1, dist) for idx, dist in zip(range(3), tr2Dists) ])
        print([ 'alpha{0} = {1:.0f} deg\n'.format(idx + 1, angle) for idx, angle in zip(range(3), tr2InnerAngles) ])
        # print('R12 = {0:.2f} px\nR13 = {1:.2f} px\nR23 = {2:.2f} px\n---'.format(R12, R13, R23))
        # print('a1 = {0:.0f} deg\na2 = {1:.0f} deg\na3 = {2:.0f} deg\n---'.format(Alpha1, Alpha2, Alpha3))
        print('---- Magnification ----')
        print([ 'mag{0} = {1:.2f}x\n'.format(idx + 1, mag) for idx, mag in zip(range(3), mags) ])
        print('---- Rotation ----')
        print([ 'phi{0} = {1:.0f} deg\n'.format(idx + 1, angle) for idx, angle in zip(range(3), rotAngles) ])
        print('---- Shifts ----')
        print([ 'dxy{0} = ({1:.1f}, {2:.1f}) px\n'.format(idx + 1, sh[0], sh[1]) for idx, sh in zip(range(3), shifts) ])
        print('------------------')
        print('Average magnification = {0:.2f}x'.format(magAvg))
        print('Average rotation = {0:.2f} deg'.format(rotAngleAvg))
        print('Average shift = ({0:.0f}, {1:.0f}) px'.format(shiftAvg[0], shiftAvg[1]))

        # img2Mag = tr.RescaleImageSki2(img2Rc, magAvg)
        # imsup.SaveAmpImage(img2Mag, 'img2_mag.png')
        img2Rot = tr.RotateImageSki2(img2Rc, rotAngleAvg, cut=False)
        imsup.SaveAmpImage(img2Rot, 'holo2.png')
        # cropCoords = imsup.DetermineCropCoordsForNewWidth(img1Rc.width, img2Rot.width)
        # img1Crop = imsup.CropImageROICoords(img1Rc, cropCoords)
        # imsup.SaveAmpImage(img1Crop, 'holo1.png')

        # ---

        # imgs1H = imsup.LinkTwoImagesSmoothlyH(img1Crop, img1Crop)
        # linkedImages1 = imsup.LinkTwoImagesSmoothlyV(imgs1H, imgs1H)
        # imgs2H = imsup.LinkTwoImagesSmoothlyH(img2Rot, img2Rot)
        # linkedImages2 = imsup.LinkTwoImagesSmoothlyV(imgs2H, imgs2H)
        #
        # img1Alg, img2Alg = cc.AlignTwoImages(linkedImages1, linkedImages2, [0, 1, 2])
        #
        # newCoords = imsup.DetermineCropCoords(img1Crop.width, img1Crop.height, img2Alg.shift)
        # newSquareCoords = imsup.MakeSquareCoords(newCoords)
        # print(newSquareCoords)
        # newSquareCoords[2:4] = list(np.array(newSquareCoords[2:4]) - np.array(newSquareCoords[:2]))
        # newSquareCoords[:2] = [0, 0]
        # print(newSquareCoords)
        #
        # img1Res = imsup.CropImageROICoords(img1Alg, newSquareCoords)
        # img2Res = imsup.CropImageROICoords(img2Alg, newSquareCoords)

        # imsup.SaveAmpImage(img1Alg, 'holo1_big.png')
        # imsup.SaveAmpImage(img2Alg, 'holo2_big.png')

        # imsup.SaveAmpImage(img1Res, 'holo1.png')
        # imsup.SaveAmpImage(img2Res, 'holo2.png')

        self.pointSets[0][:] = [ CalcNewCoords(SwitchXY(rotCenters[idx]), [-512, -512]) for idx in range(3) ]
        self.pointSets[1][:] = [ CalcNewCoords(SwitchXY(rotCenters[idx]), [-512, -512]) for idx in range(3) ]
        print(self.pointSets[0])
        print(self.pointSets[1])

        return

# --------------------------------------------------------

def LoadImageSeriesFromFirstFile(imgPath):
    imgList = imsup.ImageList()
    imgNumMatch = re.search('([0-9]+).dm3', imgPath)
    imgNumText = imgNumMatch.group(1)
    imgNum = int(imgNumText)

    while path.isfile(imgPath):
        print('Reading file "' + imgPath + '"')
        imgData = dm3.ReadDm3File(imgPath)
        imgMatrix = imsup.PrepareImageMatrix(imgData, const.dimSize)
        img = imsup.ImageWithBuffer(const.dimSize, const.dimSize, imsup.Image.cmp['CAP'], imsup.Image.mem['CPU'])
        img.LoadAmpData(np.sqrt(imgMatrix).astype(np.float32))
        # ---
        imsup.RemovePixelArtifacts(img, const.badPxThreshold)
        img.UpdateBuffer()
        # ---
        img.numInSeries = imgNum
        imgList.append(img)

        imgNum += 1
        imgNumTextNew = imgNumText.replace(str(imgNum-1), str(imgNum))
        if imgNum == 10:
            imgNumTextNew = imgNumTextNew[1:]
        imgPath = RReplace(imgPath, imgNumText, imgNumTextNew, 1)
        imgNumText = imgNumTextNew

    imgList.UpdateLinks()
    return imgList[0]

# --------------------------------------------------------

def CalcRealCoords(imgWidth, dispCoords):
    dispWidth = const.ccWidgetDim
    factor = imgWidth / dispWidth
    print(factor)
    realCoords = [ dc * factor for dc in dispCoords ]
    return realCoords

# --------------------------------------------------------

def CalcDispCoords(dispWidth, realCoords):
    imgWidth = const.dimSize
    factor = dispWidth / imgWidth
    print(factor)
    dispCoords = [ rc * factor for rc in realCoords ]
    return dispCoords

# --------------------------------------------------------

# dodac funkcje, ktora wyznacza wspolrzedne od lewego gornego rogu (a nie od srodka)

# --------------------------------------------------------

def CalcDistance(p1, p2):
    dist = np.sqrt((p1[0] - p2[0]) ** 2 + (p1[1] - p2[1]) ** 2)
    return dist

# --------------------------------------------------------

def CalcInnerAngle(a, b, c):
    alpha = np.arccos(np.abs((a*a + b*b - c*c) / (2*a*b)))
    return imsup.Degrees(alpha)

# --------------------------------------------------------

def CalcOuterAngle(p1, p2):
    dist = CalcDistance(p1, p2)
    betha = np.arcsin(np.abs(p1[0] - p2[0]) / dist)
    return imsup.Degrees(betha)

# --------------------------------------------------------

def CalcNewCoords(p1, newCenter):
    p2 = [ px - cx for px, cx in zip(p1, newCenter) ]
    return p2

# --------------------------------------------------------

def CalcRotAngle(p1, p2):
    z1 = np.complex(p1[0], p1[1])
    z2 = np.complex(p2[0], p2[1])
    phi1 = np.angle(z1)
    phi2 = np.angle(z2)
    # print(imsup.Degrees(phi1), imsup.Degrees(phi2))
    rotAngle = np.abs(imsup.Degrees(phi2 - phi1))
    # if rotAngle < 0:
    #     rotAngle = 360 - np.abs(rotAngle)
    return rotAngle

# --------------------------------------------------------

def SwitchXY(xy):
    return [xy[1], xy[0]]

# --------------------------------------------------------

def RReplace(text, old, new, occurence):
    rest = text.rsplit(old, occurence)
    return new.join(rest)

# --------------------------------------------------------

def RunTriangulationWindow():
    app = QtGui.QApplication(sys.argv)
    trWindow = TriangulateWidget()
    sys.exit(app.exec_())