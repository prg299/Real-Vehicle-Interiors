-- Developer test mod only: switches on ME: LENS development aids in the test profile.
-- MELens.addStandingPositions runs again on OnGameBoot, after this file, so the
-- calibration model is attached before any vehicle loads.
MELens = MELens or {}
MELens.calibrate = false -- set to true to hang the calibration box on the Flying Cloud
