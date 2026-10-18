# Fresh-process reload check. No reset/replenish or fixture item injection.
$code = @'
local p=getPlayer(); local it=getCell():getVehicles():iterator(); local v
while it:hasNext() do local candidate=it:next(); if candidate:getModData().MELensFinalFeatureSave then v=candidate; break end end
assert(v,"persisted feature camper missing")
local f=v:getModData().MELensFinalFeatureSave; local U,P=MELens.Utilities,MELens.Parts
local g,w=U.generatorState(v),U.waterState(v)
local function near(a,b) assert(math.abs(a-b)<.0001,tostring(a).." != "..tostring(b)) end
assert(MELens.VERSION=="2.0.6" and f.version==MELens.VERSION)
near(g.fuel,f.fuel); near(g.condition,f.condition); near(g.part:getModData().wear or 0,f.wear)
near(w.water,f.water); assert(w.tainted==f.tainted); near(U.propaneLevel(v),f.propane)
assert(not g.on and not U.isOn(v,"stove") and not U.isOn(v,"heater") and v:getModData().MELensLightsOff)
assert((MELens.Home.givenName(v) or "")==f.name,"saved name changed")
local red,green,blue=MELens.Home.paint(v)
if f.paint then near(red,f.paint.r); near(green,f.paint.g); near(blue,f.paint.b) else assert(red==nil,"saved default walls changed") end
local inv=p:getInventory():getItems()
for _,expected in ipairs(f.inventory) do local found
    for i=0,inv:size()-1 do local item=inv:get(i); if item:getID()==expected.id then found=item; break end end
    assert(found and found:getFullType()==expected.fullType,"saved inventory item changed")
    local fc=found:getFluidContainer(); near(fc and fc:getAmount() or 0,expected.amount)
end
for _,expected in ipairs(f.furniture) do local part=v:getPartById(expected.id); local item=part and part:getInventoryItem()
    assert((item and item:getFullType() or "empty")==expected.piece,"saved furniture changed")
    if expected.itemId then assert(item:getID()==expected.itemId and item:getCondition()==expected.condition,"saved furniture identity/condition changed") end
end
local floor=MELens.Loose.floorContainer(v):getItems(); local found=false
for i=0,floor:size()-1 do if floor:get(i):getID()==f.floorItem then found=true end end
assert(found,"saved floor item changed")
for _,expected in ipairs(f.floorItems or {}) do local item=MELens.Loose.floorContainer(v):getItemById(expected.id)
    assert(item and item:getFullType()==expected.fullType,"saved Floor contents changed")
end
local positions=MELens.Loose.positions(v,false) or {}
for id,expected in pairs(f.loose or {}) do local entry=positions[id]; assert(entry,"saved loose placement missing")
    for _,key in ipairs({"x","y","z","r","s"}) do near(entry[key],expected[key]) end
    assert(entry.t==expected.t,"saved loose item type changed")
end
assert(MELens.Recovery==nil and MELens.RecoveryUI==nil)
MELensTest={vehicle=v}
return {passed=true,world=getWorld():getWorld(),version=MELens.VERSION,utilityStatePreserved=true,
    inventoryIdsAndFluidPreserved=true,furniturePreserved=true,floorPreserved=true,noRecoveryUI=true,
    inventoryCount=#f.inventory,furnitureCount=#f.furniture}
'@
$state = Lua $code
$state | ConvertTo-Json -Depth 6 | Set-Content -LiteralPath (Join-Path $runPath 'feature-save-verified.json') -Encoding utf8
Shot 'features-reloaded'
Write-Host 'NATIVE_FEATURE_STATE_RELOAD_PASSED'
# Return to the parent's bounded loop for the subsequent input checks.
