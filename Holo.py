import numpy as np

import CrossCorr as cc
import Dm3Reader3_New as dm3
import ImageSupport as imsup
import Transform as tr

#-------------------------------------------------------------------

def mask_fft(fft, mid, r, out=True):
    if out:
        mfft = np.copy(fft)
        mfft[mid[0] - r:mid[0] + r, mid[1] - r:mid[1] + r] = 0
    else:
        mfft = np.zeros(fft.shape, dtype=fft.dtype)
        mfft[mid[0] - r:mid[0] + r, mid[1] - r:mid[1] + r] = np.copy(fft[mid[0] - r:mid[0] + r, mid[1] - r:mid[1] + r])
    return mfft

#-------------------------------------------------------------------

def mask_fft_center(fft, r, out=True):
    mid = (fft.shape[0] // 2, fft.shape[1] // 2)
    return mask_fft(fft, mid, r, out)

#-------------------------------------------------------------------

def find_img_max(img):
    max_xy = np.array(np.unravel_index(np.argmax(img), img.shape))
    return tuple(max_xy)

#-------------------------------------------------------------------

def insert_aperture(img, ap):
    img_ap = imsup.CopyImage(img)
    img_ap.ReIm2AmPh()
    img_ap.MoveToCPU()

    n = img_ap.width
    c = n // 2
    y, x = np.ogrid[-c:n - c, -c:n - c]
    mask = x * x + y * y > ap * ap

    img_ap.amPh.am[mask] = 0.0
    img_ap.amPh.ph[mask] = 0.0
    return img_ap

# -------------------------------------------------------------------

# zrobic tak, zeby hann window dzialal tylko na obszar NxN w srodku obrazu
def mult_by_hann_window(img, N=100):
    new_img = imsup.CopyImage(img)
    new_img.ReIm2AmPh()
    new_img.MoveToCPU()

    hann = np.hanning(img.width)
    hann_2d = np.sqrt(np.outer(hann, hann))

    hann_win = imsup.ImageWithBuffer(hann_2d.shape[0], hann_2d.shape[1])
    hann_win.LoadAmpData(hann_2d)
    imsup.SaveAmpImage(hann_win, 'hann.png')

    new_img.amPh.am *= hann_2d
    new_img.amPh.ph *= hann_2d
    return new_img

#-------------------------------------------------------------------

def rec_holo_no_ref(holo_img, rec_sz=128, ap_sz=32, mask_sz=50):
    holo_fft = cc.FFT(holo_img)
    holo_fft = cc.FFT2Diff(holo_fft)    # diff is re_im
    holo_fft.ReIm2AmPh()
    holo_fft.MoveToCPU()

    mfft = mask_fft_center(holo_fft.amPh.am, mask_sz, True)
    sband_xy = find_img_max(mfft)

    holo_fft.MoveToGPU()
    # rec_sz_half = rec_sz // 2
    # coords = [sband_xy[0] - rec_sz_half, sband_xy[1] - rec_sz_half, sband_xy[0] + rec_sz_half, sband_xy[1] + rec_sz_half]
    # sband_img = imsup.CropImageROICoords(holo_fft, coords)

    mid = holo_img.width // 2
    shift = [ mid - sband_xy[0], mid - sband_xy[1] ]
    sband_img = cc.ShiftImage(holo_fft, shift)

    sband_img_ap = mult_by_hann_window(sband_img)
    sband_img_ap = insert_aperture(sband_img_ap, ap_sz)
    imsup.SaveAmpImage(sband_img_ap, 'sband_am.png')
    imsup.SavePhaseImage(sband_img_ap, 'sband_ph.png')

    sband_img_ap = cc.Diff2FFT(sband_img_ap)
    rec_holo = cc.IFFT(sband_img_ap)

    imsup.SaveAmpImage(rec_holo, 'amp.png')
    imsup.SavePhaseImage(rec_holo, 'phs.png')

    # factor = holo_img.width / rec_sz
    # rec_holo_resc = tr.RescaleImageSki(rec_holo, factor)

    # imsup.SaveAmpImage(rec_holo_resc, 'amp.png')
    # imsup.SavePhaseImage(rec_holo_resc, 'phs.png')
    return rec_holo

#-------------------------------------------------------------------

def read_dm3_file(fpath):
    img_data, px_dims = dm3.ReadDm3File(fpath)
    imsup.Image.px_dim_default = px_dims[0]

    holo_img = imsup.ImageWithBuffer(img_data.shape[0], img_data.shape[1])
    holo_img.LoadAmpData(np.sqrt(img_data).astype(np.float32))

    return holo_img

#-------------------------------------------------------------------

holo_image = read_dm3_file('holo.dm3')
rec_holo = rec_holo_no_ref(holo_image, ap_sz=32)
