-- Exercise real startup registration with missing/partial Java, not just the gate.
do
    local M=MELens
    local old={rv=MELensRV,manager=getScriptManager,profiles=M.Profiles,parts=M.Parts}
    local declarations={}
    local vec={set=function() end}
    local position={getOffset=function() return vec end}
    local passenger={getPositionById=function() return position end}
    local script={getName=function() return "BridgeFixture" end,getPassengerCount=function() return 15 end,
        getPassengerIndex=function(_,id) return id=="MELensCabin" and 15 or -1 end,
        getPassenger=function() return passenger end,
        Load=function(_,_,text) declarations[#declarations+1]=text end}
    M.Profiles={['Base.BridgeFixture']={seatId="MELensCabin",standing={door="Door",area="Cabin",inside={0,0,0},outside={0,0,0}},
        shell={models={}},mesh={scale=.1,lift=0},hideKI5={FixtureLiner=.5}}}
    M.Parts=nil
    getScriptManager=function() return {getVehicle=function() return script end} end
    for _,rv in ipairs({false,{}, {setCutaway=function() end},
            {setKeepPlane=function() end,setCutaway=function() end,clearCutaway=function() end}}) do
        MELensRV=rv or nil
        check(M.java()==nil,"partial/missing Java bridge accepted")
        check(pcall(M.addStandingPositions),"partial Java aborts standing-position registration")
        check(#declarations>0,"partial Java skipped safe script registration")
    end
    local binds,planes=0,0
    local legacy=completeJava({});legacy.nativeMovementDistance=nil
    MELensRV=legacy
    check(M.java()==nil,"old approved Java accepted without native locomotion support")
    legacy.nativeMovementDistance=function() return 0 end
    check(M.java()==legacy,"updated locomotion bridge did not recover")
    MELensRV=completeJava({bindSeatContainer=function() binds=binds+1 end,setKeepPlane=function() planes=planes+1 end})
    check(M.java()==MELensRV,"complete bridge rejected after partial bridge")
    M.addStandingPositions()
    check(binds>0 and planes>0,"complete bridge did not register native bindings")
    -- Populating a previously incomplete table must recover; readiness is not cached.
    local late={};MELensRV=late;check(M.java()==nil,"empty late bridge accepted")
    completeJava(late);check(M.java()==late,"late API registration stays disabled")
    MELensRV,getScriptManager,M.Profiles,M.Parts=old.rv,old.manager,old.profiles,old.parts
end
