-- Developer test driver: continue a saved sandbox world from the main menu.
-- Replace WORLD before sending.
getWorld():setGameMode("Sandbox")
getWorld():setWorld("WORLD")
MainScreen.continueLatestSaveAux(true, false)
return "loading WORLD"
