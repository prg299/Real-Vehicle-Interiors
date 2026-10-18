# Invoked only inside the owned, guarded workshop-capture.ps1 lifetime.
# Usage: -GroundOnly -Scenario dev/feature-review.ps1
# The parent owns startup, screenshots, the review loop and process cleanup.
$spawn = (Get-Content -LiteralPath (Join-Path $Lens.Root 'dev\lua\spawn_one.lua') -Raw).Replace('NAME', 'Base.Trailer54FlyingCloud22').Replace('tonumber("7")', 'tonumber("-4")')
Write-Host (Lua $spawn)
[void](Wait-Lua 'local v=MELensTest and MELensTest.vehicle; return v and v:getPartCount()>0 and "spawned" or "waiting"' '^spawned$' 30)
[void](Wait-Lua 'local v=MELensTest and MELensTest.vehicle; local ok=v and MELens.canWalkIn(getPlayer(),v); return ok and "settled" or "waiting"' '^settled$' 45)
Write-Host (Lua (Get-Content -LiteralPath (Join-Path $Lens.Root 'dev\lua\walkin.lua') -Raw))
[void](Wait-Lua 'local p=getPlayer(); return p:getVehicle()~=nil and MELens.isStanding(p) and #ISTimedActionQueue.getTimedActionQueue(p).queue==0 and "standing" or "waiting"' '^standing$' 60)
[void](Lua 'getPlayer():getStats():set(CharacterStat.THIRST,0); ISUIHandler.setVisibleAllUI(false); MEMCNativeLab.releaseKeys(); return 1')
Write-Host (Lua (Get-Content -LiteralPath (Join-Path $Lens.Root 'dev\lua\feature-fixture.lua') -Raw))
[void](Lua 'local p=getPlayer(); MELens.Dashboard.open(p,MELensTest.vehicle); local w=MELens.Dashboard.instance; w:setX(45); w:setY(45); w:setVisible(true); return 1')
[void](Wait-Lua 'local w=MELens.Dashboard.instance; return w and w:isVisible() and #w.controls>0 and "controls" or "waiting"' '^controls$' 15)
Shot 'features-ready'
Write-Host 'FEATURES_READY'
# Return to the parent's bounded REVIEW_READY request loop; never quit or save.
