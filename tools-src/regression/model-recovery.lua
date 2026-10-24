-- Model caches survive native loss/adoption; committed part/item state must not change.
do
    local M,P=MELens,MELens.Parts
    local old={rv=MELensRV,profiles=M.Profiles,shown=P.shown,ghosts=P.ghosts,doors=P.shellDoorStates}
    local writes,stale=0,false
    local visible={}
    local item={getFullType=function() return P.itemType("box") end,getMaxCapacity=function() return 20 end}
    local cargo={token="same-inventory"}
    local container={capacity=20,getCapacity=function(self) return self.capacity end,getItems=function() return cargo end}
    local v={getScript=function() return {getFullName=function() return "Base.RecoveryFixture" end} end}
    local function part(id)
        local p={id=id,visible={}}
        function p:getId() return self.id end
        function p:getVehicle() return v end
        function p:setModelVisible(name,value) self.visible[name]=value;writes=writes+1 end
        function p:getInventoryItem() return self.item end
        function p:getItemContainer() return self.container end
        function p:setContainerCapacity(capacity) self.container.capacity=capacity end
        return p
    end
    local spot,shell,leaf=part(P.SPOT..1),part(P.SHELL),part("RearDoor")
    spot.item,spot.container=item,container
    leaf.item={}
    local opened=false
    function leaf:getDoor() return {isOpen=function() return opened end} end
    function v:getPartById(id) return id==P.SHELL and shell or id=="RearDoor" and leaf or spot end
    M.Profiles={['Base.RecoveryFixture']={spots={{cargo=true,length=.5,depth=.5}},
        shell={models={"floor","walls","entry"},entryModel=3,entryDoor="RearDoor"}}}
    MELensRV=completeJava({isPartModelVisible=function(p,name) return p.visible[name]==true end,
        clearStalePartModels=function(p) if stale then stale=false;p.visible={};return true end;return false end})
    P.shown,P.ghosts,P.shellDoorStates={},{},{}
    P.showPiece(spot)
    local unchanged=writes
    P.showPiece(spot)
    check(writes==unchanged,"unchanged furniture causes native model writes")
    spot.visible={};P.showPiece(spot)
    check(spot.visible.box and writes>unchanged,"lost installed model remains hidden behind Lua cache")
    check(spot.item==item and spot.container==container and container:getItems()==cargo,"render recovery replaces committed inventory")
    spot.item=nil;P.showPiece(spot)
    stale=true;spot.visible.box=true;P.showPiece(spot)
    check(not spot.visible.box and spot.item==nil,"stale default model refurnishes a cleared slot")
    local replaced=part(P.SPOT..1);replaced.item=item;replaced.container=container
    P.shown[replaced],P.ghosts[replaced]="box|","box"
    unchanged=writes;local oldCapacity=container.capacity
    P.showPiece(replaced,true)
    check(writes==unchanged and container.capacity==oldCapacity and P.shown[replaced]==nil and P.ghosts[replaced]==nil,
        "superseded UI part reference alters live models, capacity or caches")
    P.initShell(v,shell)
    unchanged=writes;P.refreshShell(v,M.profileFor(v))
    check(writes==unchanged,"unchanged shell is rebuilt")
    shell.visible={};P.refreshShell(v,M.profileFor(v))
    check(shell.visible.MELensShell1 and shell.visible.MELensShell2 and shell.visible.MELensShell3,"lost floor/walls/closed door do not recover")
    opened=true;P.syncShellDoors(v,M.profileFor(v));shell.visible.MELensShell1=false
    P.refreshShell(v,M.profileFor(v))
    check(shell.visible.MELensShell1 and not shell.visible.MELensShell3,"shell recovery closes an open rear door")
    opened=false;P.refreshShell(v,M.profileFor(v))
    check(shell.visible.MELensShell3,"cached closed rear door does not recover")
    leaf.item=nil;P.refreshShell(v,M.profileFor(v))
    check(not shell.visible.MELensShell3,"missing rear door gains an inside leaf")
    stale=true;P.refreshShell(v,M.profileFor(v))
    check(shell.visible.MELensShell1 and not shell.visible.MELensShell3,"adopted shell repair does not preserve missing door")
    local side=part("SideDoor");side.item={};local sideOpened=false
    function side:getDoor() return {isOpen=function() return sideOpened end} end
    local getPart=v.getPartById
    function v:getPartById(id) return id=="SideDoor" and side or getPart(self,id) end
    local profile=M.profileFor(v)
    profile.shell.models[4]="side_entry"
    profile.shell.extraDoors={{model=4,part="SideDoor"}}
    leaf.item={};P.initShell(v,shell)
    check(shell.visible.MELensShell3 and shell.visible.MELensShell4,"independent closed door skins missing")
    sideOpened=true;P.syncShellDoors(v,profile)
    check(shell.visible.MELensShell3 and not shell.visible.MELensShell4,"opening side door also changes rear door")
    unchanged=writes;P.syncShellDoors(v,profile)
    check(writes==unchanged,"unchanged side-door state rewrites native models every frame")
    shell.visible={};P.refreshShell(v,profile)
    check(shell.visible.MELensShell1 and shell.visible.MELensShell3 and not shell.visible.MELensShell4,
        "model recovery fills an open side door")
    sideOpened=false;P.syncShellDoors(v,profile)
    check(shell.visible.MELensShell4,"closing side door leaves a hole")
    side.item=nil;P.syncShellDoors(v,profile)
    check(not shell.visible.MELensShell4 and shell.visible.MELensShell3,"missing side door leaves a floating inside skin")
    stale=true;P.refreshShell(v,profile)
    check(shell.visible.MELensShell1 and not shell.visible.MELensShell4,"stale-part repair restores a missing side door")
    MELensRV,M.Profiles,P.shown,P.ghosts,P.shellDoorStates=old.rv,old.profiles,old.shown,old.ghosts,old.doors
end
