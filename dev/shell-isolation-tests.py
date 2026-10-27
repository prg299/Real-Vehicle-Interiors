"""Fixed-camera empty-shell model isolation in an already owned native test game.

Spawn, direct cabin entry, empty fittings, position, camera, wall options and
model visibility are explicit diagnostic fixtures. No input/workflow or final
visual acceptance is claimed. Root owns launch, save protection and shutdown.
The keep-plane baseline is rebuilt from ALL registered profile hideKI5 rules,
then the current profile's body/native/cab overrides are applied, as production
does while standing inside that vehicle. This intentionally removes
earlier ad-hoc diagnostic overrides; no raw Java keep-map getter is available.
Profiles are never edited. Each isolation restores the complete captured profile
map, including explicit planes and numeric height rules, before the next image.
"""
import argparse
import importlib.util
import json
import os
from pathlib import Path
import re
import time
import traceback

ROOT = Path(__file__).resolve().parents[1]
CASES = {
    "Base.87fordB700school": ("B700school", (1, 2, 3), "b700_door_fr", None),
    "Base.Trailer61Airflyte": ("Airflyte", (2, 3), None, None),
    "Base.Trailer87Scamp13": ("Scamp13", (2,), None, "scamp16_spare_rear"),
    "Base.Trailer87Scamp16": ("Scamp16", (2,), None, "scamp16_spare_rear"),
}
HEIGHTS = {1: "low", 2: "medium", 3: "high"}

# Capture the same whole-profile map that production addStandingPositions sets.
# Capturing it once also avoids losing the B700 rear door's explicit plane when
# one unrelated front-door/body control is reset.
BASELINE = r"""
assert(not MELensShellIsolation,"previous isolation state has not been restored")
local state={planes={},globalPlanes={},profileRules={},profileKeepPlanes={},
 windowString="",vehicle=MELensTest.vehicle}
for fullName,pr in pairs(MELens.Profiles) do
 if pr.shell then
  local rules={}
  for model,keep in pairs(pr.hideKI5 or {}) do
   local plane
   if keep==true then plane={0,0,0,1}
   elseif type(keep)=="table" and keep.plane then
    local p=keep.plane;plane={p[1],p[2],p[3],p[4]}
   else plane={0,0,1,keep/pr.mesh.scale-pr.mesh.lift} end
   state.globalPlanes[model]=plane;state.planes[model]=plane;rules[model]=plane
  end
  state.profileRules[fullName]=rules
 end
end
local pr=MELens.profileFor(state.vehicle)
for model,p in pairs(pr.bodyKeepPlanes or {}) do
 local plane={p[1],p[2],p[3],p[4]}
 state.profileKeepPlanes[model]=plane;state.planes[model]=plane
end
if pr.nativeBodyWalls and MELensRV.nativeBodyWallsActive and MELensRV.nativeBodyWallsActive() then
 for model,p in pairs(pr.nativeBodyKeepPlanes or {}) do
  local plane={p[1],p[2],p[3],p[4]}
  state.profileKeepPlanes[model]=plane;state.planes[model]=plane
 end
 if MELensRV.setNativeCabModels then
  for model,p in pairs(pr.nativeCabKeepPlanes or {}) do
   local plane={p[1],p[2],p[3],p[4]}
   state.profileKeepPlanes[model]=plane;state.planes[model]=plane
  end
 end
end
local boxes={}
for _,w in ipairs(pr.windowBoxes or {}) do
 local m=pr.mesh
 local ax,ay,az=-w.x[1]/m.scale,w.z[1]/m.scale,m.lift-w.y[1]/m.scale
 local bx,by,bz=-w.x[2]/m.scale,w.z[2]/m.scale,m.lift-w.y[2]/m.scale
 boxes[#boxes+1]=string.format("%.3f,%.3f,%.3f,%.3f,%.3f,%.3f",
  math.min(ax,bx),math.min(ay,by),math.min(az,bz),
  math.max(ax,bx),math.max(ay,by),math.max(az,bz))
end
state.windowString=table.concat(boxes,";")
state.profile=pr
state.restore=function()
 MELensRV.clearKeepPlanes()
 for model,p in pairs(state.globalPlanes) do MELensRV.setKeepPlane(model,p[1],p[2],p[3],p[4]) end
 for model,p in pairs(state.profileKeepPlanes) do MELensRV.setKeepPlane(model,p[1],p[2],p[3],p[4]) end
 if state.windowString~="" then MELensRV.setWindowBoxes(state.windowString)
 else MELensRV.clearWindowBoxes() end
end
MELensShellIsolation=state
state.restore()
return {profileRules=state.profileRules,planes=state.planes,globalPlanes=state.globalPlanes,
 profileKeepPlanes=state.profileKeepPlanes,keepPlaneOrder="global hideKI5 then body, native-body and native-cab overrides",
 windows=pr.windowBoxes or {},windowString=state.windowString,shellModels=pr.shell.models}
"""
RESTORE = "assert(MELensShellIsolation);MELensShellIsolation.restore();return true"


def load(name):
    spec = importlib.util.spec_from_file_location(name.replace("-", "_"), ROOT/"dev"/(name+".py"))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def wait_lua(h, predicate, timeout, message):
    deadline = time.monotonic()+timeout
    while not h.lua(predicate):
        h.check(time.monotonic() < deadline, message)
        time.sleep(.1)


def setup(h, name, heading):
    """Same centered empty fixture and zoom selection as cab-wall-tests.py."""
    h.lua("""MELensMedia.cameraOff();local p=getPlayer()
if p:getVehicle() then p:getVehicle():exit(p) end
ISTimedActionQueue.clear(p);p:setX(10813.5);p:setY(10140.5)
p:setLastX(10813.5);p:setLastY(10140.5);return true""")
    spawn = (ROOT/"dev/lua/spawn_one.lua").read_text().replace("NAME", name)
    spawn = spawn.replace('tonumber("7")', 'tonumber("-4")')
    spawn = spawn.replace('local HEADING = "E"', 'local HEADING = "'+heading+'"')
    h.lua(spawn)
    time.sleep(.4)
    h.lua("""local v=MELensTest.vehicle;local pr=MELens.profileFor(v);local P=MELens.Parts
for i in ipairs(pr.spots) do local part=P.spotPart(v,i)
 if part then
  if part:getItemContainer() then part:getItemContainer():getItems():clear() end
  part:setInventoryItem(nil);P.applyPiece(v,part)
 end
end
local g=MELens.WalkGrids[pr.walkGrid]
assert(v:enter(MELens.cabinSeat(v),getPlayer()))
local o=v:getScript():getModel():getOffset();local q=Vector3f.new()
v:getWorldPos(o:x(),o:y()+pr.floorY,o:z()+g.z0+#g.rows*g.cell/2,q)
MELensMedia.camera(q:x(),q:y(),v:getZ()+(o:y()+pr.floorY)/2.44949)
ISUIHandler.setVisibleAllUI(false);return true""")
    wait_lua(h, "return MELens.isStanding(getPlayer())", 15, "standing render fixture timed out")
    h.lua("""local pr=MELens.profileFor(MELensTest.vehicle);local g=MELens.WalkGrids[pr.walkGrid]
getGameTime():setTimeOfDay(12)
MELens.walkTo(getPlayer(),pr.aisleX or 0,g.z0+#g.rows*g.cell*.45);return true""")
    wait_lua(h, "return not MELens.pathing(getPlayer()) and #ISTimedActionQueue.getTimedActionQueue(getPlayer()).queue==0",
             20, "centered render fixture timed out")
    length = h.lua("local g=MELens.WalkGrids[MELens.profileFor(MELensTest.vehicle).walkGrid];return #g.rows*g.cell")
    target = .75 if length > 4 else .5
    for _ in range(8):
        zoom = h.lua("return getCore():getZoom(0)")
        if abs(zoom-target) < .02:
            break
        h.lua("getCore():doZoomScroll(0,"+str(1 if zoom < target else -1)+");return true")
        time.sleep(.2)
    h.check(abs(h.lua("return getCore():getZoom(0)")-target) < .02, "fixture zoom did not settle")


def find_mesh(survey, mesh):
    entries = []
    for line in survey.splitlines():
        match = re.match(r"^(.*?) \[mesh:(.*?)\]:", line)
        if match and match.group(2) == mesh:
            entries.append({"model": match.group(1), "mesh": mesh, "survey": line})
    if len(entries) != 1:
        raise AssertionError("expected one rendered mesh "+mesh+": "+repr(entries))
    return entries[0]


def models(h, key, door_mesh, spare_mesh):
    cfg_path = ROOT/"tools-src/blender/cfg"/("measure_"+key+".json")
    cfg = json.loads(cfg_path.read_text("utf-8-sig"))
    measure_path = ROOT/cfg["out"]
    measure = json.loads(measure_path.read_text("utf-8-sig"))
    h.check(cfg["body"] in measure["parts"], "native body missing from actual measurement")
    if door_mesh:
        h.check(door_mesh in measure["parts"], "native door missing from actual measurement")
    if spare_mesh:
        h.check(spare_mesh in measure["parts"], "native spare missing from actual measurement")
    h.lua("MELensRV.setSurvey(true);return true")
    try:
        time.sleep(.5)
        survey = h.lua("return MELensRV.surveyInfo()")
    finally:
        h.lua("MELensRV.setSurvey(false);return true")
    shell = h._sequence(h.lua("return MELens.profileFor(MELensTest.vehicle).shell.models"))
    walls = [name for name in shell if name.endswith("_walls")]
    h.check(len(walls) == 1, "expected one own wall model")
    h.check(any(line.startswith(walls[0]+" [mesh:") for line in survey.splitlines()),
            "own wall model absent from native render survey")
    body = find_mesh(survey, cfg["body"])
    result = {"ownWalls": walls[0], "nativeBody": "mesh:"+cfg["body"],
              "bodySurvey": body, "measurement": str(measure_path),
              "measurementConfig": str(cfg_path), "survey": survey}
    if door_mesh:
        door = find_mesh(survey, door_mesh)
        # Prefer the actual script alias because it takes precedence over mesh
        # aliases in Cutaway.keepPlaneFor; preserve its old rule on restoration.
        result["nativeDoor"] = ("mesh:"+door_mesh if door["model"].startswith("(unnamed ")
                                else door["model"])
        result["doorSurvey"] = door
        result["doorPart"] = "DoorFrontRight"
        result["doorSource"] = "Workshop 3110911330/mods/87fordB700/42.13/media/scripts/vehicles/template_B700_doors.txt:22-26 (DoorFrontRight file=87fordB700Doorfr)"
        h.check(result["nativeDoor"] in ("87fordB700Doorfr", "mesh:b700_door_fr"),
                "rendered front-door alias differs from verified native template")
        h.check(h.lua("local p=MELensTest.vehicle:getPartById('DoorFrontRight');return p and p:getDoor()~=nil"),
                "native front door part missing")
    if spare_mesh:
        spare = find_mesh(survey, spare_mesh)
        h.check(spare["model"] == "KI5trailersSpare",
                "rendered spare alias differs from verified native template")
        result["nativeSpare"] = spare["model"]
        result["spareSurvey"] = spare
        result["sparePart"] = "DAMNSpareTire"
        result["spareSource"] = "Workshop 3670064951/mods/KI5campers/42.20/media/scripts/vehicles/template_KI5CR_spare.txt:3-8,27-39 (KI5trailersSpare mesh=scamp16_spare_rear; DAMNSpareTire Spare0/Spare1)"
        h.check(h.lua("local p=MELensTest.vehicle:getPartById('DAMNSpareTire');return p and p:getInventoryItem()~=nil"),
                "native spare fixture part/item missing")
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--only", action="append", choices=tuple(CASES))
    parser.add_argument("--output-name", default="shell-isolation")
    args = parser.parse_args()
    run_name = os.environ["RVI_CAPTURE_RUN"]
    for name in (run_name, args.output_name):
        if not name or Path(name).name != name or name in (".", ".."):
            parser.error("run and output must each be one workspace artifact folder name")
    # Preserve the lexical workspace path: owned artifact directories are junctions.
    run = ROOT/"build/rv"/run_name
    h = load("final-feature-tests")
    h.configure(run/args.output_name)
    session = json.loads((run/"native-session.json").read_text("utf-8-sig"))
    h.SCREENS = Path(next(x.split("=", 1)[1] for x in session["command"]
                         if x.startswith("-cachedir=")))/"Screenshots"
    prior = h.lua("""local o=PZAPI.ModOptions:getOptions("RealVehicleInteriors")
return {height=o:getOption("wallHeight"):getValue(),camera=o:getOption("cameraWalls"):getValue(),
 time=getGameTime():getTimeOfDay()}""")
    active = False
    try:
        h.REPORT["scope"] = __doc__
        h.REPORT["nativeInput"] = False
        h.REPORT["fixtures"] = ["direct spawn and cabin entry", "empty furniture",
                               "centered fixed camera/zoom", "wall-height option assignment",
                               "global hideKI5 then active profile bodyKeepPlanes baseline",
                               "one-model visibility overrides"]
        h.lua("""local o=PZAPI.ModOptions:getOptions("RealVehicleInteriors")
o:getOption("cameraWalls"):setValue(true);o:apply();return true""")
        for name in args.only or CASES:
            key, choices, door_mesh, spare_mesh = CASES[name]
            for heading in ("S", "E"):
                setup(h, name, heading)
                identity = models(h, key, door_mesh, spare_mesh)
                baseline = h.lua(BASELINE)
                active = True
                h.REPORT.setdefault("modelBaselines", []).append(
                    {"vehicle": name, "heading": heading, "identity": identity, "state": baseline})
                for choice in choices:
                    h.lua(f"""local o=PZAPI.ModOptions:getOptions("RealVehicleInteriors")
o:getOption("wallHeight"):setValue({choice});o:apply();return true""")
                    time.sleep(.6)
                    h.lua(RESTORE)
                    time.sleep(.2)
                    h.check(not h.lua("return MELensRV.shaderError()"), "cutaway shader error")
                    prefix = name.split(".", 1)[1].lower()+"-"+heading.lower()+"-"+HEIGHTS[choice]
                    frames = {"baseline": h.capture(prefix+"-baseline")}
                    controls = []
                    if not door_mesh:
                        controls.append(("windows-cleared", None))
                    controls += [("own-walls-hidden", identity["ownWalls"]),
                                 ("native-body-hidden", identity["nativeBody"])]
                    if door_mesh:
                        controls.append(("native-door-front-right-hidden", identity["nativeDoor"]))
                    if spare_mesh:
                        controls.append(("native-spare-hidden", identity["nativeSpare"]))
                    try:
                        for label, alias in controls:
                            h.lua(RESTORE)
                            if alias is None:
                                h.lua("MELensRV.clearWindowBoxes();return true")
                            else:
                                h.lua("MELensRV.setKeepPlane("+json.dumps(alias)+",0,0,0,1);return true")
                            time.sleep(.35)
                            frames[label] = h.capture(prefix+"-"+label)
                    finally:
                        h.lua(RESTORE)
                    time.sleep(.35)
                    frames["restored"] = h.capture(prefix+"-restored")
                    h.record(prefix, {"profileBaseline": baseline},
                             {"restoredProfileMap": True, "restoredWindowString": baseline["windowString"]},
                             frames=frames, controls=[{"label": label, "alias": alias,
                             "previousPlane": baseline["planes"].get(alias) if alias else None}
                             for label, alias in controls], nativeInput=False,
                             sameCamera=True, emptyFixture=True, visualReview="pending")
                h.lua(RESTORE)
                h.lua("MELensShellIsolation=nil;return true")
                active = False
        h.REPORT["unverified"] = ["human visual adjudication", "production UI input",
                                  "arbitrary pre-existing Java diagnostic keep-map overrides"]
        h.write_report("passed")
        return 0
    except Exception:
        error = traceback.format_exc()
        print(error, flush=True)
        h.write_report("failed", error)
        return 1
    finally:
        restore_error = None
        if active:
            try:
                h.lua(RESTORE)
                h.lua("MELensShellIsolation=nil;return true")
            except Exception as error:
                restore_error = error
                h.REPORT["restoreError"] = str(error)
                h.write_report("failed", "keep-plane/window restoration failed")
        h.lua(f"""MELensRV.setSurvey(false)
local o=PZAPI.ModOptions:getOptions("RealVehicleInteriors")
o:getOption("wallHeight"):setValue({int(prior["height"])})
o:getOption("cameraWalls"):setValue({str(prior["camera"]).lower()});o:apply()
getGameTime():setTimeOfDay({prior["time"]})
local p=getPlayer();if p:getVehicle() then p:getVehicle():exit(p) end
MELensMedia.cameraOff();ISUIHandler.setVisibleAllUI(true);return true""")
        if restore_error is not None:
            raise RuntimeError("keep-plane/window restoration failed") from restore_error


if __name__ == "__main__":
    raise SystemExit(main())
