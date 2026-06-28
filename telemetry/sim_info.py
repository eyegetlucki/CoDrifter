"""
Assetto Corsa shared memory interface.
Standard community implementation — DO NOT MODIFY.
Maps SPageFilePhysics, SPageFileGraphic, and SPageFileStatic from AC shared memory.
"""
import mmap
import ctypes
from ctypes import c_int32, c_float, c_wchar


class SPageFilePhysics(ctypes.Structure):
    _pack_ = 4
    _fields_ = [
        ('packetId', c_int32),
        ('gas', c_float),
        ('brake', c_float),
        ('fuel', c_float),
        ('gear', c_int32),
        ('rpms', c_int32),
        ('steerAngle', c_float),
        ('speedKmh', c_float),
        ('velocity', c_float * 3),
        ('accG', c_float * 3),
        ('wheelSlip', c_float * 4),
        ('wheelLoad', c_float * 4),
        ('wheelsPressure', c_float * 4),
        ('wheelAngularSpeed', c_float * 4),
        ('tyreWear', c_float * 4),
        ('tyreDirtyLevel', c_float * 4),
        ('tyreCoreTemperature', c_float * 4),
        ('camberRAD', c_float * 4),
        ('suspensionTravel', c_float * 4),
        ('drs', c_float),
        ('tc', c_float),
        ('heading', c_float),
        ('pitch', c_float),
        ('roll', c_float),
        ('cgHeight', c_float),
        ('carDamage', c_float * 5),
        ('numberOfTyresOut', c_int32),
        ('pitLimiterOn', c_int32),
        ('abs', c_float),
        ('kersCharge', c_float),
        ('kersInput', c_float),
        ('autoShifterOn', c_int32),
        ('rideHeight', c_float * 2),
        ('turboBoost', c_float),
        ('ballast', c_float),
        ('airDensity', c_float),
        ('airTemp', c_float),
        ('roadTemp', c_float),
        ('localAngularVel', c_float * 3),
        ('finalFF', c_float),
        ('performanceMeter', c_float),
        ('engineBrake', c_int32),
        ('ersRecoveryLevel', c_int32),
        ('ersPowerLevel', c_int32),
        ('ersHeatCharging', c_int32),
        ('ersIsCharging', c_int32),
        ('kersCurrentKJ', c_float),
        ('drsAvailable', c_int32),
        ('drsEnabled', c_int32),
        ('brakeTemp', c_float * 4),
        ('clutch', c_float),
        ('tyreTempI', c_float * 4),
        ('tyreTempM', c_float * 4),
        ('tyreTempO', c_float * 4),
        ('isAIControlled', c_int32),
        ('tyreContactPoint', c_float * 4 * 3),
        ('tyreContactNormal', c_float * 4 * 3),
        ('tyreContactHeading', c_float * 4 * 3),
        ('brakeBias', c_float),
        ('localVelocity', c_float * 3),
    ]


class SPageFileGraphic(ctypes.Structure):
    _pack_ = 4
    _fields_ = [
        ('packetId', c_int32),
        ('status', c_int32),
        ('session', c_int32),
        ('currentTime', c_wchar * 15),
        ('lastTime', c_wchar * 15),
        ('bestTime', c_wchar * 15),
        ('split', c_wchar * 15),
        ('completedLaps', c_int32),
        ('position', c_int32),
        ('iCurrentTime', c_int32),
        ('iLastTime', c_int32),
        ('iBestTime', c_int32),
        ('sessionTimeLeft', c_float),
        ('distanceTraveled', c_float),
        ('isInPit', c_int32),
        ('currentSectorIndex', c_int32),
        ('lastSectorTime', c_int32),
        ('numberOfLaps', c_int32),
        ('tyreCompound', c_wchar * 33),
        ('replayTimeMultiplier', c_float),
        ('normalizedCarPosition', c_float),
        ('carCoordinates', c_float * 3),
        ('penaltyTime', c_float),
        ('flag', c_int32),
        ('idealLineOn', c_int32),
        ('isInPitLane', c_int32),
        ('surfaceGrip', c_float),
        ('mandatoryPitDone', c_int32),
        ('windSpeed', c_float),
        ('windDirection', c_float),
        ('isSetupMenuVisible', c_int32),
        ('mainDisplayIndex', c_int32),
        ('secondaryDisplayIndex', c_int32),
        ('tc', c_int32),
        ('tcCut', c_int32),
        ('engineMap', c_int32),
        ('abs', c_int32),
        ('fuelXLap', c_float),
        ('rainLights', c_int32),
        ('flashingLights', c_int32),
        ('lightsStage', c_int32),
        ('exhaustTemperature', c_float),
        ('wiperLV', c_int32),
        ('driverStintTotalTimeLeft', c_int32),
        ('driverStintTimeLeft', c_int32),
        ('rainTyres', c_int32),
    ]


class SPageFileStatic(ctypes.Structure):
    _pack_ = 4
    _fields_ = [
        ('smVersion', c_wchar * 15),
        ('acVersion', c_wchar * 15),
        ('numberOfSessions', c_int32),
        ('numCars', c_int32),
        ('carModel', c_wchar * 33),
        ('track', c_wchar * 33),
        ('playerName', c_wchar * 33),
        ('playerSurname', c_wchar * 33),
        ('playerNick', c_wchar * 33),
        ('sectorCount', c_int32),
        ('maxTorque', c_float),
        ('maxPower', c_float),
        ('maxRpm', c_int32),
        ('maxFuel', c_float),
        ('suspensionMaxTravel', c_float * 4),
        ('tyreRadius', c_float * 4),
        ('maxTurboBoost', c_float),
        ('deprecated_1', c_float),
        ('deprecated_2', c_float),
        ('penaltiesEnabled', c_int32),
        ('aidFuelRate', c_float),
        ('aidTireRate', c_float),
        ('aidMechanicalDamage', c_float),
        ('aidAllowTyreBlankets', c_int32),
        ('aidStability', c_float),
        ('aidAutoClutch', c_int32),
        ('aidAutoBlip', c_int32),
        ('hasDRS', c_int32),
        ('hasERS', c_int32),
        ('hasKERS', c_int32),
        ('kersMaxJ', c_float),
        ('engineBrakeSettingsCount', c_int32),
        ('ersPowerControllerCount', c_int32),
        ('trackSplineLength', c_float),
        ('trackConfiguration', c_wchar * 33),
        ('ersMaxJ', c_float),
        ('isTimedRace', c_int32),
        ('hasExtraLap', c_int32),
        ('carSkin', c_wchar * 33),
        ('reversedGridPositions', c_int32),
        ('pitWindowStart', c_int32),
        ('pitWindowEnd', c_int32),
    ]


class SimInfo:
    def __init__(self):
        self._physics_mmap = None
        self._graphics_mmap = None
        self._static_mmap = None
        self.physics = None
        self.graphics = None
        self.static = None
        self._connected = False

    def connect(self):
        try:
            self._physics_mmap = mmap.mmap(-1, ctypes.sizeof(SPageFilePhysics), "Local\\acpmf_physics")
            self._graphics_mmap = mmap.mmap(-1, ctypes.sizeof(SPageFileGraphic), "Local\\acpmf_graphics")
            self._static_mmap = mmap.mmap(-1, ctypes.sizeof(SPageFileStatic), "Local\\acpmf_static")
            self.physics = SPageFilePhysics.from_buffer(self._physics_mmap)
            self.graphics = SPageFileGraphic.from_buffer(self._graphics_mmap)
            self.static = SPageFileStatic.from_buffer(self._static_mmap)
            self._connected = True
            return True
        except Exception:
            self._connected = False
            return False

    def is_connected(self):
        return self._connected

    def close(self):
        self._connected = False
        for m in (self._physics_mmap, self._graphics_mmap, self._static_mmap):
            if m:
                try:
                    m.close()
                except Exception:
                    pass
