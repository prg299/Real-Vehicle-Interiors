-- Production menu dispatch and action adaptation; native appearance/input is separate.
do
    local M,A,C=MELens,MELens.Animals,MELens.AnimalContext
    local saved={triggerEvent=triggerEvent,AnimalContextMenu=AnimalContextMenu,
        luautils=luautils,ISTimedActionQueue=ISTimedActionQueue,ISPetAnimal=ISPetAnimal,CompanionDogs=CompanionDogs}
    local inside,characterAt,standingThen,walkTo,facePoint=A.inside,M.Parts.characterAt,M.standingThen,M.walkTo,M.facePoint
    local pickupNew=MELensPickUpAnimal.new
    local v={getModData=function(self) return self.data end,data={}}
    local actorSquare={}
    local p={getPlayerNum=function() return 2 end,getCurrentSquare=function() return actorSquare end}
    local animal={getVehicle=function() return v end,getAnimalID=function() return 123 end,
        isDead=function() return false end,getHealth=function() return 1 end,
        isExistInTheWorld=function() return false end,getFeedByHandAnim=function() return 'nativeFeed' end,
        getCurrentSquare=function(self) return self.current end,setCurrent=function(self,square) self.current=square end}
    v.data[A.KEY]={['123']={x=.3,z=0}}
    A.inside=function(player) if player==p then return v,{} end end
    M.Parts.characterAt=function() return 0,0 end
    M.standingThen=function(_,fn) fn() end
    local paths=0
    M.walkTo=function(_,_,_,fn) paths=paths+1;fn() end
    local turned=false
    M.facePoint=function(player,x,z) check(player==p and x==.3 and z==0,'animal action targets its old world position');return turned end
    local standFor=M.LooseUI.standFor
    M.LooseUI.standFor=function() return 0,0 end
    local queue={}
    local add=function(action) queue[#queue+1]=action end
    local getUp=function(_,action) add(action) end
    local walk=function() return false end
    ISTimedActionQueue={add=add,addGetUpAndThen=getUp}
    luautils={walkAdj=walk}
    local nativeCalls=0
    local native=function(target,arg) nativeCalls=nativeCalls+1;check(target==animal and arg==p,'native menu target changed');return 'native result' end
    local sub={options={{name='Native carry',target=animal,param1=p,onSelect=native,iconTexture='native grab',toolTip='native tooltip'}}}
    local dashboard=function() error('unrelated dashboard was invoked') end
    local context={options={{name='Dashboard',onSelect=dashboard}},getSubMenu=function() return sub end}
    triggerEvent=function(event,playerNum,menu,animals,test)
        check(animal:getCurrentSquare()==actorSquare,'vanilla menu cannot measure an interior animal without a world square')
        check(event=='OnClickedAnimalForContext' and playerNum==2 and menu==context and animals[1]==animal and test==false,
            'interior menu does not use the real world animal event contract')
        menu.options[#menu.options+1]={name='Native animal',iconTexture='native species',subOption=1}
    end
    C.menu(p,animal,context)
    check(animal:getCurrentSquare()==nil,'native menu leaked the borrowed world square onto a trailer animal')
    local eventBuilder=triggerEvent
    triggerEvent=function() error('menu builder fixture') end
    check(not pcall(C.menu,p,animal,context) and animal:getCurrentSquare()==nil,'failed native menu builder leaks a world square')
    triggerEvent=eventBuilder
    check(#context.options==2 and context.options[2].name=='Native animal' and context.options[2].iconTexture=='native species',
        'native menu hierarchy, label or icon changed')
    check(context.options[1].onSelect==dashboard and sub.options[1].toolTip=='native tooltip','unrelated menu or native tooltip changed')
    check(sub.options[1].onSelect(animal,p)=='native result' and nativeCalls==1,'native command callback was replaced or lost arguments')
    check(ISTimedActionQueue.add==add and luautils.walkAdj==walk,'menu callback leaked a shared API override')
    local action={Type='ISCDWaterDog',character=p,animal=animal,handModelItem='native bottle',
        isValid=function() return true end,start=function(self) self.nativeStart=true end,
        setActionAnim=function(self,anim) self.anim=anim end,setOverrideHandModels=function(self,item) self.hand=item end}
    C.invoke(p,animal,function()
        check(luautils.walkAdj(p,nil),'native callback still tries outside-square walking')
        ISTimedActionQueue.add({Type='ISWalkToTimedActionF',character=p})
        ISTimedActionQueue.addGetUpAndThen(p,action)
    end)
    check(#queue==1 and queue[1]==action and paths==1,'native action did not use shared interior walking or retained an outside walk')
    check(action:isValid(),'valid native inventory action rejected inside')
    check(action:waitToStart(),'native animal action starts before the cabin turn')
    turned=true;check(not action:waitToStart(),'native animal action never starts after the cabin turn')
    action:start()
    check(action.nativeStart and action.anim=='nativeFeed' and action.hand=='native bottle','native action setup/held model lost')
    v.data[A.KEY]['123'].x=5
    check(not action:isValid(),'stale distant animal action bypasses cabin reach')
    v.data[A.KEY]['123'].x=.3
    local ok=pcall(C.invoke,p,animal,function() error('callback fixture') end)
    check(not ok and ISTimedActionQueue.add==add and ISTimedActionQueue.addGetUpAndThen==getUp and luautils.walkAdj==walk,
        'failed native callback leaked global routing overrides')
    local owner=true
    CompanionDogs={isOwnedBy=function() return owner end}
    function animal:getData() return {getMaxSize=function() return 1 end,getMinSize=function() return 1 end} end
    function animal:isBaby() return false end
    function animal:isFemale() return false end
    function animal:clearVariable(name) self.cleared=name end
    function p:setVariable(name,value) self[name]=value end
    ISPetAnimal={start=function(self) self.nativePetSetup=true end}
    local pet={Type='ISCDPetDog',animal=animal,character=p,isValid=function() return false end,
        start=function() end,stop=function() end,forceStop=function() end,perform=function(self) self.nativeEffect=true end}
    C.invoke(p,animal,function() ISTimedActionQueue.addGetUpAndThen(p,pet) end)
    check(pet:isValid(),'trailer dog cannot use the native pet action')
    pet:start()
    check(pet.nativePetSetup and p.animal=='raccoonboar' and p.AnimalSizeY==1,'native dog pet setup loses its pose or emits a zero-size division')
    owner=false;check(not pet:isValid(),'native dog pet action ignores changed ownership');owner=true
    pet:perform()
    check(pet.nativeEffect and animal.cleared=='idleAction','native pet cleanup loses its effect or leaves petting active')
    ISPetAnimal={isValid=function() return false end}
    A.wrapPetAction()
    check(ISPetAnimal.isValid({animal=animal,character=p}),'native pet action cannot reach a nearby cabin animal')
    v.data[A.KEY]['123'].x=5
    check(not ISPetAnimal.isValid({animal=animal,character=p}),'native pet distance bypassed on authority')
    A.inside=function() return nil end
    check(not ISPetAnimal.isValid({animal=animal,character=p}),'outside native pet validation changed')
    local beforeCalls=nativeCalls
    sub.options[1].onSelect(animal,p)
    check(nativeCalls==beforeCalls,'stale interior menu invokes a world callback after the animal leaves')
    local beforePaths=paths
    check(C.invoke(p,animal,native,animal,p)=='native result' and paths==beforePaths,'outside callback gained interior routing')
    A.inside,M.Parts.characterAt,M.standingThen,M.walkTo=inside,characterAt,standingThen,walkTo
    M.facePoint=facePoint
    M.LooseUI.standFor=standFor;MELensPickUpAnimal.new=pickupNew
    for key,value in pairs(saved) do _G[key]=value end
    if saved.ISPetAnimal==nil then ISPetAnimal=nil end
    if saved.AnimalContextMenu==nil then AnimalContextMenu=nil end
    if saved.triggerEvent==nil then triggerEvent=nil end
    if saved.luautils==nil then luautils=nil end
    if saved.CompanionDogs==nil then CompanionDogs=nil end
end
