-- One readiness gate for the optional client bridge. A stale exposed class can
-- exist without the API used by the accompanying Lua; truthiness is insufficient.
MELens = MELens or {}
local required = { "setKeepPlane", "bindSeatContainer", "setCutaway", "clearCutaway",
    "isPartModelVisible", "clearStalePartModels" }
local warnedBridge, warnedMethod

function MELens.java()
    local rv = MELensRV
    if not rv then return nil end -- Dedicated servers and approval-disabled clients.
    for _, name in ipairs(required) do
        if type(rv[name]) ~= "function" then
            if warnedBridge ~= rv or warnedMethod ~= name then
                print("[RealVehicleInteriors] Java API incomplete: missing " .. name
                    .. ". Update Real Vehicle Interiors and ZombieBuddy, approve RealVehicleInteriors.jar"
                    .. " and restart the game. Check for an older local copy overriding Workshop.")
                warnedBridge, warnedMethod = rv, name
            end
            return nil
        end
    end
    warnedBridge, warnedMethod = nil, nil
    return rv
end
