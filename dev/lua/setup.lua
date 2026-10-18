-- Developer test driver: make the test world screenshot-friendly and scriptable.
UIManager.setShowLuaDebuggerOnError(false)
-- a Lua error while the game started stops it in the Lua debugger window (nothing ticks, no action runs): go on
pcall(function() doLuaDebuggerAction("Resume") end)
getGameTime():setTimeOfDay(12)
local climate = getClimateManager()
climate:stopWeatherAndThunder()
local fog = climate:getClimateFloat(ClimateManager.FLOAT_FOG_INTENSITY)
fog:setEnableAdmin(true)
fog:setAdminValue(0)
local ui = UIManager.getUI()
for i = 0, ui:size() - 1 do
    local t = ui:get(i):getTable()
    if t and (t.Type == "SurvivalGuide" or t.Type == "ISCharacterInfoWindow") then t:setVisible(false) end
end
-- a cold makes the test character cough and sneeze with a speech bubble that ends up in the captures
local ok = pcall(function()
    local bd = getPlayer():getBodyDamage()
    bd:setHasACold(false)
    bd:setColdStrength(0)
    bd:setSneezeCoughActive(0)
end)
-- no zombies in the test world: hordes from video shoots are saved with it and mob the test spot (a hit
-- reaction blocks the walk-in, and they stand in every capture)
pcall(function()
    local list = getCell():getZombieList()
    for i = list:size() - 1, 0, -1 do
        local z = list:get(i)
        z:removeFromWorld()
        z:removeFromSquare()
    end
end)
-- the test character must not die (a bus tipped over by a clashing spawn killed one mid-run): god mode
pcall(function() getPlayer():setGodMod(true) end)
-- the test character wears clothes (captures and screenshots for posts: no underwear)
pcall(function()
    local p = getPlayer()
    local inv = p:getInventory()
    local worn = p:getWornItems()
    if worn:size() == 0 then
        for _, t in ipairs({ "Base.Tshirt_DefaultTEXTURE_TINT", "Base.Trousers_DefaultTEXTURE_TINT", "Base.Shoes_Random" }) do
            local item = inv:AddItem(t)
            if item then p:setWornItem(item:getBodyLocation(), item) end
        end
        p:resetModel()
        triggerEvent("OnClothingUpdated", p)
    end
end)
return "ready"
