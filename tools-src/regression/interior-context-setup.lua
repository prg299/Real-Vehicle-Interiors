-- Engine doubles for dispatch guards; real mouse/menu acceptance is native.
InteriorContextFixture={old={}}
local F=InteriorContextFixture
for _,name in ipairs({'getSpecificPlayer','getCore','isGamePaused','getMouseXScaled','getMouseYScaled','ISContextMenu','UIManager'}) do
    F.old[name]=_G[name]
end
F.old.profileFor=MELens.profileFor
F.old.inVanillaSeat=MELens.inVanillaSeat
F.old.pick=MELens.Interact.pick
F.old.fill=MELens.Interact.fillMenu
for _,name in ipairs({'OnRightMouseDown','OnRightMouseUp'}) do
    local event={callbacks={}}
    event.Add=function(fn) table.insert(event.callbacks,fn) end
    Events[name]=event
end
F.player={}
function F.player:isDead() return F.dead end
function F.player:isAsleep() return F.asleep end
function F.player:isAiming() return F.aiming end
function F.player:getVehicle() return F.vehicle end
getSpecificPlayer=function() return F.player end
getCore=function() return {isDoingTextEntry=function() return F.typing end} end
isGamePaused=function() return F.paused end
getMouseXScaled=function() return 17 end
getMouseYScaled=function() return 19 end
MELens.profileFor=function() return F.profile end
MELens.inVanillaSeat=function() return F.cab end
UIManager={getPicked=function() return F.picked end}
MELens.Interact.pick=function() return F.hit end
MELens.Interact.fillMenu=function(player,menu)
    check(player==F.player,'context filled for a different player')
    F.fills=F.fills+1
    menu.empty=F.empty
end
ISContextMenu={get=function(player,x,y)
    check(player==0 and x==24 and y==32,'context coordinates/player changed')
    return {isEmpty=function(self) return self.empty end,setVisible=function(self,v) F.visible=v end}
end}
function F.reset()
    F.dead,F.asleep,F.aiming,F.typing,F.paused,F.cab=false,false,false,false,false,false
    F.vehicle,F.profile,F.hit={},{},{kind='piece',index=4}
    F.picked=nil;F.fills=0;F.visible=false;F.empty=false
    MELens.InteriorContext.pressedAt=nil
end
