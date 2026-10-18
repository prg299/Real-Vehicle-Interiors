# Verify native persisted furniture, contents and utility state after a fresh process load.
$ErrorActionPreference = 'Stop'
$code = @'
local p=getPlayer(); local inv=p:getInventory(); local vehicles=getCell():getVehicles():iterator(); local v
while vehicles:hasNext() do local candidate=vehicles:next(); if candidate:getModData().MELensLifecycleFixture then v=candidate; break end end
assert(v,"Saved camper fixture missing"); local f=v:getModData().MELensLifecycleFixture
local function contains(container,id) for i=0,container:getItems():size()-1 do if container:getItems():get(i):getID()==id then return true end end; return false end
for _,id in ipairs(f.inventory) do assert(contains(inv,id),"Saved inventory ID changed") end
local P,U=MELens.Parts,MELens.Utilities; local bare=v:getPartById(f.bare)
assert(bare:getInventoryItem()==nil,"Deliberately empty spot refurnished")
assert(contains(bare:getItemContainer(),f.cargo),"Orphan storage item changed")
assert(contains(MELens.Loose.floorContainer(v),f.loose),"Floor item changed")
local gen=U.generatorState(v); local water=U.waterState(v)
assert(gen.fuel==7.5 and gen.on==false and gen.condition==37,"Saved generator changed")
assert(gen.part:getModData().wear==.42,"Generator wear changed")
assert(water.water==22 and water.tainted==true,"Saved water changed")
assert(MELens.VERSION=="2.0.5" and MELens.Recovery==nil and MELens.RecoveryUI==nil)
MELensTest={vehicle=v}
return {world=getWorld():getWorld(),version=MELens.VERSION,inventoryIdsPreserved=true,emptyLayoutPreserved=true,orphanCargoPreserved=true,floorPreserved=true,fuelWaterConditionPreserved=true,noRecoveryUI=true}
'@
$state = Lua $code
$state | ConvertTo-Json -Depth 6 | Set-Content -LiteralPath (Join-Path $runPath 'save-review-verified.json') -Encoding utf8
Shot 'saved-layout-after-reload'
Write-Host 'NATIVE_SAVE_RELOAD_PASSED'
[IO.File]::WriteAllText((Join-Path $runPath 'request.json'),'{"action":"stop"}')
