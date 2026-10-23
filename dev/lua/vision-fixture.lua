-- Owned disposable world only. Spawn/position fixtures; natural AI keeps running.
local p,v=getPlayer(),MELensTest.vehicle
assert(p and v,"vision fixture requires a native test vehicle")
-- The media harness starts with population disabled. Enable AI/spawning only in
-- this disposable test sandbox before creating the specifically owned observers.
getSandboxOptions():set("Zombies",4)
if MELensVisionTest then MELensVisionTest.clear() end
local T={player=p,vehicle=v,zombies={}}
MELensVisionTest=T
p:setInvisible(false);p:setGhostMode(false);p:setGodMod(true)
function T.spawn(x,z)
    local pos=Vector3f.new();local o=v:getScript():getModel():getOffset()
    v:getWorldPos(o:x()+x,0,o:z()+z,pos)
    local list=addZombiesInOutfit(math.floor(pos:x()),math.floor(pos:y()),0,1,nil,0)
    assert(list and list:size()==1,"native zombie spawn failed")
    local zombie=list:get(0)
    zombie:setX(pos:x());zombie:setY(pos:y());zombie:setLastX(pos:x());zombie:setLastY(pos:y())
    zombie:ensureOnTile();zombie:faceLocation(p:getX(),p:getY())
    local direction=Vector2.new(p:getX()-zombie:getX(),p:getY()-zombie:getY());direction:normalize()
    zombie:setForwardDirection(direction)
    T.zombies[#T.zombies+1]=zombie
    return #T.zombies
end
function T.clear()
    for _,z in ipairs(T.zombies) do z:removeFromWorld();z:removeFromSquare() end
    T.zombies={}
end
function T.snapshot(index)
    local z=T.zombies[index or 1]
    local o=v:getScript():getModel():getOffset();local a,b=Vector3f.new(),Vector3f.new()
    v:getPassengerLocalPos(v:getSeat(p),a);v:getLocalPos(z:getX(),z:getY(),z:getZ(),b)
    return {native=MEMCNativeLab.zombieInfo(z,p),vision=MELensRV.visionInfo(z,p),
        x=z:getX(),y=z:getY(),playerX=p:getX(),playerY=p:getY(),
        localX=b:x()-o:x(),localZ=b:z()-o:z(),insideX=a:x()-o:x(),insideZ=a:z()-o:z(),
        worldAge=getGameTime():getWorldAgeHours(),inside=MELens.isStanding(p)}
end
-- Forced native spotting is a deterministic hook contract, not an automatic
-- acquisition claim. Both calls run in one game-thread callback at one world age.
function T.pair(x,z,old)
    T.clear();T.spawn(x,z);T.spawn(x,z)
    local a,b=T.zombies[1],T.zombies[2]
    local age=getGameTime():getWorldAgeHours()
    MEMCNativeLab.visionMask(false);MEMCNativeLab.forceSpot(a,p,old)
    local control=MEMCNativeLab.zombieInfo(a,p)
    MEMCNativeLab.visionMask(true);MEMCNativeLab.forceSpot(b,p,old)
    local treatment=MEMCNativeLab.zombieInfo(b,p)
    -- Repeating an unchanged blocked input cannot create or clear a target.
    MEMCNativeLab.forceSpot(b,p,old)
    local unchanged=MEMCNativeLab.zombieInfo(b,p)
    -- A previously acquired target remains native memory; entering a hull does
    -- not make our advice erase it or overwrite its last seen coordinates.
    MEMCNativeLab.forceSpot(a,p,old)
    return {control=control,treatment=treatment,unchanged=unchanged,memory=MEMCNativeLab.zombieInfo(a,p),
        ageBefore=age,ageAfter=getGameTime():getWorldAgeHours(),sample=T.snapshot(2)}
end
return true
