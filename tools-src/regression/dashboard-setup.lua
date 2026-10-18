-- Minimal load-time UI services. Dashboard checks below are engine-double contracts,
-- never a replacement for the separate real native mouse/UI evidence.
MELensDashboardRegressionSaved = {}
for _, name in ipairs({ "ISPanel", "UIFont", "getTextManager", "isMouseButtonDown",
        "getPlayerContextMenu", "ISContextMenu", "JoypadState", "getMouseX", "getMouseY", "getSoundManager" }) do
    MELensDashboardRegressionSaved[name] = _G[name]
end
UIFont = { Small = "Small", Medium = "Medium" }
function getTextManager()
    return { getFontHeight = function() return 14 end, MeasureStringX = function(_, _, text) return #text * 7 end }
end
ISPanel = { update = function() end }
function ISPanel:derive(_)
    local child = {}; setmetatable(child, { __index = self }); return child
end
