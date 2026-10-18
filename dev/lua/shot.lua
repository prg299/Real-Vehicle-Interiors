-- Developer test driver: full-window screenshot into the test profile's Screenshots folder.
-- Replace NAME before sending (lua.ps1 / curl callers substitute it).
getCore():TakeFullScreenshot("NAME.png")
return "NAME.png"
