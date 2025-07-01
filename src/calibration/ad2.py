from ctypes import cdll, c_int, c_double, c_byte, byref, create_string_buffer
import math
import time


def measure_acrms() -> float:
    dwf = cdll.LoadLibrary("libdwf.so")

    hdwf = c_int()
    sts = c_byte()
    secLog = 1.0  # logging rate in seconds
    nSamples = 8000
    rgdSamples = (c_double * nSamples)()
    cValid = c_int(0)

    version = create_string_buffer(16)
    dwf.FDwfGetVersion(version)
    print("DWF Version: " + str(version.value))

    print("Opening first device")
    dwf.FDwfDeviceOpen(c_int(-1), byref(hdwf))

    if hdwf.value == 0:
        szerr = create_string_buffer(512)
        dwf.FDwfGetLastErrorMsg(szerr)
        print(str(szerr.value))
        print("failed to open device")
        quit()

    # 0 = the device will only be configured when FDwf###Configure is called
    dwf.FDwfDeviceAutoConfigureSet(hdwf, c_int(0))

    # set up acquisition
    dwf.FDwfAnalogInChannelEnableSet(hdwf, c_int(0), c_int(1))
    dwf.FDwfAnalogInChannelRangeSet(hdwf, c_int(0), c_double(5))
    dwf.FDwfAnalogInAcquisitionModeSet(hdwf, c_int(1))  # acqmodeScanShift
    dwf.FDwfAnalogInFrequencySet(hdwf, c_double(nSamples / secLog))
    dwf.FDwfAnalogInBufferSizeSet(hdwf, c_int(nSamples))
    dwf.FDwfAnalogInConfigure(hdwf, c_int(1), c_int(0))

    # wait at least 2 seconds for the offset to stabilize
    time.sleep(1)

    # begin acquisition
    dwf.FDwfAnalogInConfigure(hdwf, c_int(0), c_int(1))

    time.sleep(secLog)
    dwf.FDwfAnalogInStatus(hdwf, c_int(1), byref(sts))
    dwf.FDwfAnalogInStatusSamplesValid(hdwf, byref(cValid))

    iChannel = 0
    dwf.FDwfAnalogInStatusData(hdwf, c_int(iChannel), byref(rgdSamples), cValid)  # get channel 1 data
    dc = 0
    for i in range(nSamples):
        dc += rgdSamples[i]
    dc /= nSamples
    dcrms = 0
    acrms = 0
    for i in range(nSamples):
        dcrms += rgdSamples[i] ** 2
        acrms += (rgdSamples[i] - dc) ** 2
    dcrms /= nSamples
    dcrms = math.sqrt(dcrms)
    acrms /= nSamples
    acrms = math.sqrt(acrms)
    print(f"CH:{iChannel+1} DC:{dc:.3f}V DCRMS:{dcrms:.3f}V ACRMS:{acrms:.3f}V")

    dwf.FDwfDeviceCloseAll()

    return acrms
