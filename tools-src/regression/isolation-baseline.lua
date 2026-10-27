-- A diagnostic restore must preserve the cab plane that keeps its dashboard.
do
    local M=MELens
    local old={rv=MELensRV,profiles=M.Profiles,profileFor=M.profileFor,test=MELensTest,isolation=MELensShellIsolation}
    local planes={}
    local function noop() end
    local profile={mesh={scale=.1,lift=0},shell={models={}},hideKI5={FixtureCab=true,FixtureRoof=true},
        nativeBodyWalls=true,bodyKeepPlanes={FixtureOrdinary={0,1,0,3}},
        nativeBodyKeepPlanes={FixtureRoof={0,0,0,1}},nativeCabKeepPlanes={FixtureCab={0,-1,0,12.4}}}
    M.Profiles={Fixture=profile}
    M.profileFor=function() return profile end
    MELensTest={vehicle={}}
    MELensRV={setKeepPlane=function(model,a,b,c,d) planes[model]={a,b,c,d} end,
        clearKeepPlanes=function() planes={} end,clearWindowBoxes=noop,
        nativeBodyWallsActive=function() return true end,setNativeCabModels=noop}
    MELensShellIsolation=nil
    local baseline=regressionIsolationBaseline()
    check(planes.FixtureCab[2]==-1 and planes.FixtureCab[4]==12.4,
        "empty diagnostic hides the cab through its global ceiling rule")
    MELensRV.setKeepPlane("FixtureCab",0,0,0,1)
    MELensRV.setKeepPlane("FixtureTemporary",0,0,0,1)
    MELensShellIsolation.restore()
    check(planes.FixtureCab[2]==-1 and planes.FixtureCab[4]==12.4 and planes.FixtureTemporary==nil,
        "diagnostic restore loses cab clipping or retains an isolation override")
    check(planes.FixtureOrdinary[4]==3 and planes.FixtureRoof[4]==1,
        "diagnostic restore loses another profile override")
    MELensShellIsolation=nil
    MELensRV.setNativeCabModels=nil
    regressionIsolationBaseline()
    check(planes.FixtureCab[2]==0 and planes.FixtureCab[4]==1,
        "intermediate bridge receives unsupported cab keep planes")
    MELensRV,M.Profiles,M.profileFor,MELensTest,MELensShellIsolation=old.rv,old.profiles,old.profileFor,old.test,old.isolation
    regressionIsolationBaseline=nil
end
