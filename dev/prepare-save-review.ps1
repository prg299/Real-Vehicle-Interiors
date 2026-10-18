# Native save lifecycle fixtures in the disposable profile, within the capture guard.
$ErrorActionPreference = 'Stop'
$previous = Get-Content -LiteralPath (Join-Path $Lens.Out 'workshop-20261017-recovery2/recovery-native-result.json') -Raw | ConvertFrom-Json
$ids = @($previous.ids.PSObject.Properties | Sort-Object Name | ForEach-Object Value) -join ','
$code = @'
local p=getPlayer(); local inv=p:getInventory(); local expected={IDS}
for _,id in ipairs(expected) do local found=false; for i=0,inv:getItems():size()-1 do if inv:getItems():get(i):getID()==id then found=true end end; assert(found,"Saved inventory ID missing: "..id) end
assert(MELens.VERSION=="2.0.5"); assert(MELens.Recovery==nil and MELens.RecoveryUI==nil)
local vehicles=getCell():getVehicles():iterator(); local v
while vehicles:hasNext() do local candidate=vehicles:next(); if candidate:getModData().MELensRecoveryReviewIds then v=candidate; break end end
assert(v,"Saved camper missing")
for i=0,v:getPartCount()-1 do local part=v:getPartByIndex(i); if string.find(part:getId(),"^MELens") then local c=part:getItemContainer(); assert(not c or c:isEmpty(),"Saved empty storage refilled") end end
local P,U=MELens.Parts,MELens.Utilities
local bare=P.spotPart(v,2); bare:setInventoryItem(nil); P.applyPiece(v,bare)
local cargo=bare:getItemContainer():AddItem("Base.Hammer")
local floor=MELens.Loose.floorContainer(v); local loose=floor:AddItem("Base.Pencil")
local gen=U.generatorState(v).part; gen:getModData().fuel=7.5; gen:getModData().on=false; gen:getModData().wear=.42; gen:setCondition(37)
local water=U.waterState(v).part; water:getModData().water=22; water:getModData().tainted=true
v:getModData().MELensLifecycleFixture={cargo=cargo:getID(),loose=loose:getID(),bare=bare:getId(),inventory=expected}
GameWindow.save(true)
return {world=getWorld():getWorld(),version=MELens.VERSION,priorInventoryPreserved=true,emptyStoragePreserved=true,cargo=cargo:getID(),loose=loose:getID()}
'@
$state = Lua $code.Replace('IDS',$ids)
$state | ConvertTo-Json -Depth 6 | Set-Content -LiteralPath (Join-Path $runPath 'save-review-prepared.json') -Encoding utf8
Shot 'saved-layout-before-reload'
Write-Host 'NATIVE_SAVE_REVIEW_PREPARED'
[IO.File]::WriteAllText((Join-Path $runPath 'request.json'),'{"action":"stop"}')
