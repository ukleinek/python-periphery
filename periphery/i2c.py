import os
import ctypes
import array
import fcntl

class I2CException(IOError):
    pass

class CI2CMessage(ctypes.Structure):
    _fields_ = [
        ("addr", ctypes.c_ushort),
        ("flags", ctypes.c_ushort),
        ("len", ctypes.c_ushort),
        ("buf", ctypes.POINTER(ctypes.c_ubyte)),
    ]

class CI2CIocTransfer(ctypes.Structure):
    _fields_ = [
        ("msgs", ctypes.POINTER(CI2CMessage)),
        ("nmsgs", ctypes.c_uint),
    ]

class I2C:
    # Constants scraped from <linux/i2c-dev.h> and <linux/i2c.h>
    I2C_IOC_FUNCS       = 0x705
    I2C_IOC_RDWR        = 0x707
    I2C_FUNC_I2C        = 0x1
    I2C_M_TEN           = 0x0010
    I2C_M_RD            = 0x0001
    I2C_M_STOP          = 0x8000
    I2C_M_NOSTART       = 0x4000
    I2C_M_REV_DIR_ADDR  = 0x2000
    I2C_M_IGNORE_NAK    = 0x1000
    I2C_M_NO_RD_ACK     = 0x0800
    I2C_M_RECV_LEN      = 0x0400

    class Message:
        def __init__(self, data, read=False, flags=0):
            if not isinstance(data, bytes) and not isinstance(data, bytearray) and not isinstance(data, list):
                raise TypeError("Invalid data type, should be bytes, bytearray, or list.")
            if not isinstance(read, bool):
                raise TypeError("Invalid read type, should be boolean.")
            if not isinstance(flags, int):
                raise TypeError("Invalid flags type, should be integer.")

            self.data = data
            self.read = read
            self.flags = flags

    def __init__(self, devpath):
        self._fd = None
        self._devpath = None
        self._open(devpath)

    def __del__(self):
        self.close()

    def _open(self, devpath):
        # Open i2c device
        try:
            self._fd = os.open(devpath, os.O_RDWR)
        except OSError as e:
            raise I2CException(e.errno, "Opening I2C device: " + e.strerror)

        self._devpath = devpath

        # Query supported functions
        buf = array.array('I', [0])
        try:
            fcntl.ioctl(self._fd, I2C.I2C_IOC_FUNCS, buf, True)
        except OSError as e:
            self.close()
            raise I2CException(e.errno, "Querying supported functions: " + e.strerror)

        # Check that I2C_RDWR ioctl() is supported on this device
        if (buf[0] & I2C.I2C_FUNC_I2C) == 0:
            self.close()
            raise I2CException(None, "I2C not supported on device %s." % devpath)

    def close(self):
        if self._fd is None:
            return

        try:
            os.close(self._fd)
        except OSError as e:
            raise I2CException(e.errno, "Closing I2C device: " + e.strerror)

        self._fd = None

    # Methods

    def transfer(self, address, messages):
        if not isinstance(messages, list):
            raise TypeError("Invalid messages type, should be list of I2C.Message.")
        elif len(messages) == 0:
            raise ValueError("Invalid messages data, should be non-zero length.")

        # Convert I2C.Message messages to CI2CMessage messages
        cmessages = (CI2CMessage * len(messages))()
        for i in range(len(messages)):
            # Convert I2C.Message data to bytes
            if isinstance(messages[i].data, bytes):
                data = messages[i].data
            elif isinstance(messages[i].data, bytearray):
                data = bytes(messages[i].data)
            elif isinstance(messages[i].data, list):
                data = bytes(bytearray(messages[i].data))

            cmessages[i].addr = address
            cmessages[i].flags = messages[i].flags | (I2C.I2C_M_RD if messages[i].read else 0)
            cmessages[i].len = len(data)
            cmessages[i].buf = ctypes.cast(ctypes.create_string_buffer(data, len(data)), ctypes.POINTER(ctypes.c_ubyte))

        # Prepare transfer structure
        i2c_xfer = CI2CIocTransfer()
        i2c_xfer.nmsgs = len(cmessages)
        i2c_xfer.msgs = cmessages

        # Transfer
        try:
            fcntl.ioctl(self._fd, I2C.I2C_IOC_RDWR, i2c_xfer, False)
        except IOError as e:
            raise I2CException(e.errno, "I2C transfer: " + e.strerror)

        # Update any read I2C.Message messages
        for i in range(len(messages)):
            if messages[i].read:
                data = [cmessages[i].buf[j] for j in range(cmessages[i].len)]
                # Convert read data to type used in I2C.Message messages
                if isinstance(messages[i].data, list):
                    messages[i].data = data
                elif isinstance(messages[i].data, bytearray):
                    messages[i].data = bytearray(data)
                elif isinstance(messages[i].data, bytes):
                    messages[i].data = bytes(bytearray(data))

    # Immutable properties

    @property
    def fd(self):
        return self._fd

    @property
    def devpath(self):
        return self._devpath

    # String representation

    def __str__(self):
        return "I2C (device=%s, fd=%d)" % (self.devpath, self.fd)
