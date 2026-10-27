do
    local F=InteriorContextFixture
    local function click(duration)
        emit('OnRightMouseDown');now=now+(duration or 70);emit('OnRightMouseUp',24,32)
    end
    F.reset();click()
    check(F.fills==1 and F.visible,'virtual furniture without a native world pick has no menu')
    F.reset();emit('OnRightMouseUp',24,32)
    check(F.fills==0,'release without an unconsumed press opened a world menu')
    F.reset();click(500)
    check(F.fills==0,'long aiming hold opened a furniture menu')
    for _,name in ipairs({'dead','asleep','aiming','typing','paused','cab'}) do
        F.reset();F[name]=true;click()
        check(F.fills==0,'rejected context input leaked for '..name)
    end
    for _,name in ipairs({'profile','hit'}) do
        F.reset();F[name]=nil;click()
        check(F.fills==0,'outside/unpicked input opened a furniture menu: '..name)
    end
    F.reset();F.picked={tile={getObjectIndex=function() return 0 end}};click()
    check(F.fills==0,'native world picker path was duplicated')
    F.reset();F.picked=42;click()
    check(F.fills==0,'native opaque pick was indexed or duplicated')
    F.reset();F.empty=true;click()
    check(F.fills==1 and not F.visible,'an empty context menu became visible')
    for _,name in ipairs({'getSpecificPlayer','getCore','isGamePaused','getMouseXScaled','getMouseYScaled','ISContextMenu','UIManager'}) do
        _G[name]=F.old[name]
    end
    MELens.profileFor,MELens.inVanillaSeat=F.old.profileFor,F.old.inVanillaSeat
    MELens.Interact.pick,MELens.Interact.fillMenu=F.old.pick,F.old.fill
end
