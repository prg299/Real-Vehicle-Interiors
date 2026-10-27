-- Model caches survive native loss/adoption; committed part/item state must not change.
do
    local M,P=MELens,MELens.Parts
    local old={rv=MELensRV,profiles=M.Profiles,shown=P.shown,ghosts=P.ghosts,
        doors=P.shellDoorStates,wheels=P.shellWheelStates}
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
        function p:setModelVisible(name,value,...)
            check(select('#',...)==0,"shell binding passes extra Lua returns to the native two-argument method")
            self.visible[name]=value;writes=writes+1
        end
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
    P.shown,P.ghosts,P.shellDoorStates,P.shellWheelStates={},{},{},{}
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

    -- F350's optional flat arch replaces only appended surfaces. Exercise the
    -- production init/sync/recovery paths; this bridge double models Java's result,
    -- not shader execution or native visual acceptance.
    profile.nativeBodyWalls=true
    profile.nativeWheelArch={sideX=1.062,contour={{-2.8,-.088},{-2.5,.264},{-2.2,-.088}}}
    for i,name in ipairs({"support","rear_skin","jambs","wheel_covers","wheel_floor","wheel_wall"}) do
        profile.shell.models[i+4]=name
    end
    profile.shell.wheelCoversModel,profile.shell.wheelFloorModel,profile.shell.wheelWallModel=8,9,10
    local cutVehicle,flat,shaderError=v,true,false
    local function flatActive() return flat and not shaderError end
    MELensRV.flatWheelArchActive=flatActive
    MELensRV.getCutawayVehicle=function() return cutVehicle end
    local function wheelState(active,label)
        check(shell.visible.MELensShell1==true,label..": base floor hidden")
        check(shell.visible.MELensShell8==not active,label..": fallback covers wrong")
        check(shell.visible.MELensShell9==active,label..": flat floor wrong")
        check(shell.visible.MELensShell10==active,label..": arch wall wrong")
        check(shell.visible.MELensShell3 and not shell.visible.MELensShell4,
            label..": wheel switch changed closed rear/missing side door")
    end
    P.initShell(v,shell);wheelState(true,"active init")
    unchanged=writes;P.syncShellDoors(v,profile);P.refreshShell(v,profile)
    check(writes==unchanged,"unchanged flat arch rewrites native models")
    shell.visible={};P.refreshShell(v,profile);wheelState(true,"lost active bindings")
    stale=true;P.refreshShell(v,profile);wheelState(true,"stale active bindings")

    shaderError=true;P.syncShellDoors(v,profile);wheelState(false,"shader-error inactive")
    stale=true;P.refreshShell(v,profile);wheelState(false,"stale shader fallback")
    shaderError=false;P.syncShellDoors(v,profile);wheelState(true,"shader recovery")
    flat=false;P.syncShellDoors(v,profile);wheelState(false,"API inactive")
    flat=true;P.syncShellDoors(v,profile);wheelState(true,"API reactivated")

    cutVehicle={};P.syncShellDoors(v,profile);wheelState(false,"other vehicle instance")
    stale=true;P.refreshShell(v,profile);wheelState(false,"stale other instance")
    cutVehicle=v;P.syncShellDoors(v,profile);wheelState(true,"current vehicle restored")
    profile.nativeBodyWalls=false;P.syncShellDoors(v,profile)
    wheelState(false,"SWAT-style inherited metadata without native opt-in")
    profile.nativeBodyWalls=true;P.syncShellDoors(v,profile);wheelState(true,"native opt-in restored")

    MELensRV.flatWheelArchActive=nil
    P.syncShellDoors(v,profile);wheelState(false,"older Java API")
    P.initShell(v,shell);wheelState(false,"older Java initialization")
    stale=true;P.refreshShell(v,profile);wheelState(false,"older Java stale recovery")
    MELensRV.flatWheelArchActive=flatActive
    P.syncShellDoors(v,profile);wheelState(true,"optional API restored")
    profile.nativeWheelArch=nil;P.syncShellDoors(v,profile);wheelState(false,"missing arch metadata")
    check(spot.item==nil and spot.container==container and container:getItems()==cargo,
        "wheel-surface recovery refurnishes or replaces committed inventory")

    profile.panel={x=-.74,y=-.025,z=1.655}
    profile.nativePanel={x=-.839,y=-.025,z=1.655}
    profile.shell.models[11],profile.shell.models[12]="panel_legacy","panel_native"
    profile.shell.legacyPanelModel,profile.shell.nativePanelModel=11,12
    local nativePanel=true
    MELensRV.nativeBodyWallsActive=function() return nativePanel end
    local function panelState(active,label)
        check(shell.visible.MELensShell11==not active,label..": legacy panel visibility")
        check(shell.visible.MELensShell12==active,label..": native panel visibility")
        check(P.panelFor(v,profile)==(active and profile.nativePanel or profile.panel),label..": rendered panel and interaction anchor disagree")
        check(shell.visible.MELensShell1==true,label..": panel switch hid base floor")
    end
    P.syncShellDoors(v,profile);panelState(true,"native panel enter")
    unchanged=writes;P.syncShellDoors(v,profile);P.refreshShell(v,profile)
    check(writes==unchanged,"unchanged native panel rewrites bindings")
    shell.visible={};P.refreshShell(v,profile);panelState(true,"native panel binding recovery")
    nativePanel=false;P.syncShellDoors(v,profile);panelState(false,"native panel fallback")
    nativePanel=true;cutVehicle={};P.syncShellDoors(v,profile);panelState(false,"panel other vehicle")
    cutVehicle=v;P.syncShellDoors(v,profile);panelState(true,"panel current vehicle restored")
    MELensRV.nativeBodyWallsActive=nil;P.syncShellDoors(v,profile);panelState(false,"panel older Java")
    stale=true;P.refreshShell(v,profile);panelState(false,"panel older Java recovery")
    profile.shell.models[13]="floor_perimeter"
    profile.shell.nativeFloorModel=13
    MELensRV.nativeBodyWallsActive=function() return true end
    P.syncShellDoors(v,profile)
    check(shell.visible.MELensShell13==true,"native floor perimeter not visible for occupied vehicle")
    shell.visible.MELensShell13=false;P.refreshShell(v,profile)
    check(shell.visible.MELensShell13==true,"native floor perimeter binding did not recover")
    cutVehicle={};P.syncShellDoors(v,profile)
    check(shell.visible.MELensShell13==false,"native floor perimeter leaked to another vehicle")
    cutVehicle=v;MELensRV.nativeBodyWallsActive=nil;P.syncShellDoors(v,profile)
    check(shell.visible.MELensShell13==false,"native floor perimeter exposed on older Java")
    check(spot.item==nil and spot.container==container and container:getItems()==cargo,
        "panel recovery refurnishes or replaces committed inventory")

    profile.shell.models[14],profile.shell.models[15]="fixed_window_return","door_window_return"
    profile.shell.windowReturns={{model=14,part="WindowRearLeft"},
        {model=15,part="WindowSide",parent="SideDoor"}}
    MELensRV.nativeBodyWallsActive=function() return true end
    side.item={};sideOpened=false;P.syncShellDoors(v,profile)
    check(shell.visible.MELensShell14 and shell.visible.MELensShell15,
        "closed native window lining returns not visible")
    unchanged=writes;P.syncShellDoors(v,profile);P.refreshShell(v,profile)
    check(writes==unchanged,"unchanged window returns rewrite native bindings")
    sideOpened=true;P.syncShellDoors(v,profile)
    check(shell.visible.MELensShell14 and not shell.visible.MELensShell15,
        "opening door leaves its window surround floating in the fixed wall")
    sideOpened=false;side.item=nil;P.syncShellDoors(v,profile)
    check(shell.visible.MELensShell14 and not shell.visible.MELensShell15,
        "missing door restores its window surround")
    side.item={};P.syncShellDoors(v,profile)
    shell.visible.MELensShell14=false;shell.visible.MELensShell15=false;P.refreshShell(v,profile)
    check(shell.visible.MELensShell14 and shell.visible.MELensShell15,
        "lost window-return bindings do not recover")
    cutVehicle={};P.syncShellDoors(v,profile)
    check(not shell.visible.MELensShell14 and not shell.visible.MELensShell15,
        "window returns leak into another occupied vehicle")
    cutVehicle=v;MELensRV.nativeBodyWallsActive=nil;P.syncShellDoors(v,profile)
    check(not shell.visible.MELensShell14 and not shell.visible.MELensShell15,
        "window returns appear on the legacy bridge")
    profile.shell.models[16]="variant_window_return"
    profile.shell.windowReturns[3]={model=16,part="WindowRearRight",scripts={"Base.86fordE150LBMWradio"}}
    MELensRV.nativeBodyWallsActive=function() return true end
    P.syncShellDoors(v,profile)
    check(not shell.visible.MELensShell16,"radio-only window surround leaks onto cargo variant")
    local fixtureScript=v.getScript
    v.getScript=function() return {getFullName=function() return "Base.86fordE150LBMWradio" end} end
    P.syncShellDoors(v,profile)
    check(shell.visible.MELensShell16,"radio-specific glazing surround is absent")
    v.getScript=fixtureScript
    P.syncShellDoors(v,profile)
    check(not shell.visible.MELensShell16,"variant change leaves a floating surround")
    local windowBridge=MELensRV
    MELensRV=nil
    P.syncShellDoors(v,profile)
    check(not shell.visible.MELensShell14 and not shell.visible.MELensShell15 and not shell.visible.MELensShell16,
        "declined bridge leaves native window returns visible")
    MELensRV=windowBridge
    check(spot.item==nil and spot.container==container and container:getItems()==cargo,
        "window-return refresh changes committed furniture or inventory")

    MELensRV,M.Profiles,P.shown,P.ghosts,P.shellDoorStates,P.shellWheelStates=
        old.rv,old.profiles,old.shown,old.ghosts,old.doors,old.wheels
end
