import me.lens.rv.RV;

/** Production state contract only; no renderer, native input or engine doubles. */
public final class CutawayStateCheck {
    private static int assertions = 4;

    private static void check(boolean condition, String reason) {
        if (!condition) throw new AssertionError(reason);
        assertions++;
    }

    private static void checkNative(float d, float expected, String reason) throws Exception {
        checkNative(d, false, false, expected, reason);
    }

    private static void checkNative(float d, boolean near, boolean door, float expected, String reason) throws Exception {
        var state = RV.class.getDeclaredField("nativeCutInset");
        state.setAccessible(true);
        Object inset = state.get(null);
        var apply = inset.getClass().getDeclaredMethod("apply", float.class, boolean.class, boolean.class);
        apply.setAccessible(true);
        float actual = (float) apply.invoke(inset, d, near, door);
        if (actual != expected) throw new AssertionError(reason + ": " + actual + " != " + expected);
        assertions++;
    }

    public static void main(String[] args) throws Exception {
        var height = RV.class.getDeclaredField("cutFrontTopZ");
        height.setAccessible(true);
        var cab = RV.class.getDeclaredField("cutFrontCabY");
        cab.setAccessible(true);
        RV.setCutFront(14);
        RV.setCutFrontTop(-12);
        RV.setCutFrontCab(18);
        check(cab.getFloat(null) == 18f, "original full cab boundary lost behind lower door bay");
        RV.setCutFrontCab(Double.NaN);
        check(cab.getFloat(null) == 18f, "invalid full cab boundary replaced committed value");
        if (height.getFloat(null) != -12f) throw new AssertionError("explicit cab height lost");
        RV.setCutFront(21);
        check(cab.getFloat(null) == 1e9f, "previous vehicle full cab boundary leaked");
        if (height.getFloat(null) != -1e9f) throw new AssertionError("previous vehicle cab height leaked");
        RV.setCutFrontTop(-45);
        if (height.getFloat(null) != -45f) throw new AssertionError("next vehicle cab height ignored");
        RV.clearCutFront();
        check(cab.getFloat(null) == 1e9f, "clear retained full cab boundary");
        if (height.getFloat(null) != -1e9f) throw new AssertionError("clear retained cab height");
        RV.setCutaway(null, 0, 0, -1, 10);
        RV.setNativeCutInset(2, 15);
        checkNative(10, 12, "native far cut did not lower by mesh distance");
        checkNative(14, 15, "native near cut crossed the floor limit");
        checkNative(16, 15, "pre-existing low cut bypassed the floor limit");
        RV.setNativeCutInset(0, 1);
        checkNative(10, 10, "zero control was clamped or shifted");
        RV.setNativeCutInset(-2, 15);
        checkNative(10, 10, "negative inset raised the native cut");
        RV.setNativeCutInset(Double.NaN, 15);
        checkNative(10, 10, "invalid inset contaminated the cut");
        RV.setNativeCutInset(2, Double.POSITIVE_INFINITY);
        checkNative(10, 10, "invalid floor limit was accepted");
        RV.setCutaway(null, 0, 0, -2, 10);
        RV.setNativeCutInset(2, 20);
        checkNative(10, 14, "mesh distance ignored the plane normal length");
        RV.setCutaway(null, 0, 0, -1, 10);
        checkNative(10, 10, "previous vehicle inset leaked into new cutaway");
        RV.setNativeCutInset(2, 15);
        RV.clearCutaway();
        checkNative(10, 10, "clear retained the native cut inset");
        RV.setCutaway(null, 0, 0, -1, 10);
        RV.setNativeCutInsets(1, 2, 4, 20);
        checkNative(10, false, false, 11, "body far offset was not independent");
        checkNative(10, true, false, 12, "body near offset was not independent");
        checkNative(10, false, true, 14, "door far cut used body offset");
        checkNative(10, true, true, 14, "door near cut used body offset");
        checkNative(19.5f, false, false, 20, "body far cut crossed floor limit");
        checkNative(18, true, true, 20, "door cut crossed floor limit");
        RV.setNativeCutInsets(1, 0, 4, 9);
        checkNative(10, true, false, 10, "zero near control was clamped by another offset");
        RV.setNativeCutInsets(1, -2, 4, 20);
        checkNative(10, false, false, 10, "invalid near offset did not reset atomic state");
        RV.setNativeCutInsets(1, 2, Double.NaN, 20);
        checkNative(10, true, false, 10, "invalid door offset did not reset atomic state");
        RV.setNativeCutInset(2, 20);
        checkNative(10, true, false, 12, "uniform shorthand lost near behavior");
        checkNative(10, false, true, 12, "uniform shorthand lost door behavior");
        RV.setCutaway(null, 0, 0, -1, 10);
        checkNative(10, true, true, 10, "new cutaway retained door inset");
        RV.setNativeCutInsets(1, 2, 4, 20);
        RV.clearCutaway();
        checkNative(10, true, false, 10, "clear retained independent near inset");
        var lining = RV.class.getDeclaredField("bodyLining");
        lining.setAccessible(true);
        Object none = lining.get(null);
        RV.setBodyLining(.55, .57, .59);
        if (lining.get(null) == none) throw new AssertionError("valid lining ignored");
        assertions++;
        check(!RV.bodyLiningPlainActive(), "default finish changed the approved KI5 treatment");
        check(RV.setBodyLiningMaterial("MELensShell_b700_walls", .09, 1.34, 17.98), "valid curved material rejected");
        check(RV.bodyLiningMaterialActive(), "curved material did not activate");
        var finishMaterial = Class.forName("me.lens.rv.NativeFinish").getDeclaredField("material");
        finishMaterial.setAccessible(true);
        RV.setBodyLiningBoundaryFinish(true);
        Object optedBoundary = finishMaterial.get(null);
        RV.setBodyLiningMaterial("MELensShell_b700_walls", .09, 1.34, 17.98);
        check(!finishMaterial.get(null).equals(optedBoundary), "boundary opt-in leaked to replacement material");
        check(!RV.setBodyLiningMaterial("../external", .09, 1.34, 17.98), "external texture path accepted");
        check(!RV.bodyLiningMaterialActive(), "invalid material retained previous state");
        check(!RV.setBodyLiningMaterial("MELensShell_b700_walls", Double.NaN, 1.34, 17.98), "nonfinite material scale accepted");
        RV.setBodyLiningMaterial("MELensShell_b700_walls", .09, 1.34, 17.98);
        RV.setBodyLiningPlain(true);
        check(RV.bodyLiningPlainActive(), "stock inward finish opt-in ignored");
        check(RV.setBodyLiningStockMetal("vehicle_vanseatsshell",.09,.56640625,.35546875,
                .3427734375,.2861328125,.4970703125,.3896484375,1.10,.7425), "qualified stock metal rejected");
        check(RV.bodyLiningStockMetalActive(), "stock metal did not activate");
        check(!RV.setBodyLiningStockMetal("../external",.09,.56,.35,.34,.28,.49,.38,1.10,.7425),
                "external stock texture path accepted");
        check(!RV.bodyLiningStockMetalActive(), "invalid stock configuration retained finish");
        check(!RV.setBodyLiningStockMetal("vehicle_vanseatsshell",.09,Double.NaN,.35,.34,.28,.49,.38,1.10,.7425),
                "nonfinite stock UV accepted");
        check(!RV.setBodyLiningStockMetal("vehicle_vanseatsshell",.08,.56,.35,.34,.28,.49,.38,1.10,.7425),
                "stock material scale disagreed with native geometry");
        RV.setBodyLiningStockMetal("vehicle_vanseatsshell",.09,.56,.35,.34,.28,.49,.38,1.10,.7425);
        RV.setBodyLiningPlain(false);
        check(!RV.bodyLiningStockMetalActive(), "stock metal leaked to KI5 finish selection");
        check(!RV.setBodyLiningStockMetal("vehicle_vanseatsshell",.09,.56,.35,.34,.28,.49,.38,1.10,.7425),
                "stock metal enabled on non-vanilla finish");
        RV.setBodyLiningPlain(true);
        RV.setBodyLiningStockMetal("vehicle_vanseatsshell",.09,.56,.35,.34,.28,.49,.38,1.10,.7425);
        RV.setBodyLiningDebug(true);
        check(RV.bodyLiningPlainActive(), "diagnostic mode lost the selected finish");
        RV.setCutaway(null, 0, 0, -1, 10);
        check(!RV.bodyLiningPlainActive(), "plain finish leaked from stock to KI5 cutaway");
        check(!RV.bodyLiningMaterialActive(), "curved material leaked to next vehicle");
        check(!RV.bodyLiningStockMetalActive(), "stock metal leaked to next vehicle");
        RV.setBodyLiningPlain(true);
        check(!RV.bodyLiningPlainActive(), "plain finish enabled without a lining");
        if (lining.get(null) != none) throw new AssertionError("lining leaked to another vehicle");
        assertions++;
        RV.setBodyLining(Double.NaN, .57, .59);
        if (lining.get(null) != none) throw new AssertionError("invalid lining accepted");
        assertions++;
        RV.setBodyLining(.55, .57, .59);
        RV.setBodyLiningPlain(true);
        RV.setBodyLiningDebug(true);
        RV.clearCutaway();
        check(!RV.bodyLiningPlainActive(), "plain finish survived exit");
        if (lining.get(null) != none) throw new AssertionError("clear retained diagnostic lining");
        assertions++;
        RV.setNativeBodyWalls(true);
        RV.setNativeCabPartition(true);
        check(RV.nativeCabPartitionActive(), "measured cab partition opt-in ignored");
        RV.setNativeBodyModels("PanelLeft,PanelRight");
        RV.setNativeCabModels("CabInterior,mesh:dashboard");
        RV.setNativeArchTrimModels("RearFenderLeft,RearFenderRight");
        var archModels = RV.class.getDeclaredField("nativeArchTrimModels");
        archModels.setAccessible(true);
        check(((java.util.Set<?>) archModels.get(null)).size() == 2, "rear fitting aliases ignored");
        check(!RV.nativeArchTrimActive(), "rear fitting trim active without a measured arch");
        var cabModels = RV.class.getDeclaredField("nativeCabModels");
        cabModels.setAccessible(true);
        check(((java.util.Set<?>) cabModels.get(null)).contains("mesh:dashboard"), "cab material-preservation aliases ignored");
        var nativeModels = RV.class.getDeclaredField("nativeBodyModels");
        nativeModels.setAccessible(true);
        if (!RV.nativeBodyWallsActive()) throw new AssertionError("native wall opt-in ignored");
        assertions++;
        RV.setCutaway(null, 0, 0, -1, 10);
        if (RV.nativeBodyWallsActive()) throw new AssertionError("native walls leaked to next vehicle");
        check(!RV.nativeCabPartitionActive(), "cab partition leaked to next vehicle");
        check(((java.util.Set<?>) nativeModels.get(null)).isEmpty(), "structural panel aliases leaked to next vehicle");
        check(((java.util.Set<?>) cabModels.get(null)).isEmpty(), "native cab aliases leaked to next vehicle");
        check(((java.util.Set<?>) archModels.get(null)).isEmpty(), "rear fitting aliases leaked to next vehicle");
        assertions++;
        RV.setNativeBodyWalls(true);
        RV.setNativeCabPartition(true);
        RV.setNativeBodyModels("PanelRight");
        RV.setNativeCabModels("CabInterior");
        RV.setNativeArchTrimModels("RearFenderLeft");
        RV.clearCutaway();
        check(((java.util.Set<?>) cabModels.get(null)).isEmpty(), "native cab aliases survived clear");
        check(((java.util.Set<?>) archModels.get(null)).isEmpty(), "rear fitting aliases survived clear");
        if (RV.nativeBodyWallsActive()) throw new AssertionError("native walls survived clear");
        check(!RV.nativeCabPartitionActive(), "cab partition survived exit");
        check(((java.util.Set<?>) nativeModels.get(null)).isEmpty(), "structural panel aliases survived exit");
        check(RV.setNativeRoofCut("Roof,mesh:roof", .6, 0,0,0,0,0,0, 0,0,0,0), "qualified roof-normal rule rejected");
        check(!RV.nativeRoofCutsActive(), "roof rules active outside native mode");
        RV.setNativeBodyWalls(true);
        check(RV.nativeRoofCutsActive(), "roof rules not active in native mode");
        check(!RV.setNativeRoofCut("Roof", Double.NaN, 0,0,0,0,0,0, 0,0,0,0), "invalid roof normal accepted");
        check(!RV.setNativeRoofCut("Roof", -1, 0,0,0,0,0,0, 0,0,0,0), "unqualified whole-model roof cut accepted");
        check(!RV.setNativeRoofCut("Roof", -1, 0,0,1,1,0,2, 0,0,0,0), "degenerate measured roof region accepted");
        check(!RV.setNativeRoofCut("Roof", -1, 0,0,0,1,1,1, .1,.2,1.1,.4), "invalid roof UV accepted");
        check(RV.nativeRoofCutsActive(), "rejected roof input discarded committed rules");
        RV.setCutaway(null, 0,0,-1,10);
        RV.setNativeBodyWalls(true);
        check(!RV.nativeRoofCutsActive(), "roof cut leaked to another vehicle");
        check(RV.setNativeRoofCut("Roof", -1, 1,1,1,-1,-1,-1, .1,.2,.3,.4), "reversed measured roof bounds rejected");
        RV.clearCutaway();
        RV.setNativeBodyWalls(true);
        check(!RV.nativeRoofCutsActive(), "roof cut survived exit");
        for (int i=0; i<5; i++) check(RV.setNativeRoofCut("Roof"+i, .6, 0,0,0,0,0,0, 0,0,0,0),
            "unrelated model cuts incorrectly share the per-draw limit");
        RV.clearNativeRoofCuts();
        for (int i=0; i<4; i++) check(RV.setNativeRoofCut("Roof", .6, 0,0,0,0,0,0, 0,0,0,0), "valid per-draw roof rule rejected");
        check(!RV.setNativeRoofCut("mesh:roof", .6, 0,0,0,0,0,0, 0,0,0,0), "script/mesh union can overflow shader roof slots");
        RV.clearNativeRoofCuts();
        check(RV.setNativeSurfaceCut("Body,mesh:body", -1, -1,-2,-3,1,2,3, .6,.8,.99,.99),
            "qualified embedded fitting cut rejected");
        check(RV.nativeSurfaceCutsActive() && RV.nativeRoofCutsActive(), "surface and roof evaluators diverged");
        check(!RV.setNativeSurfaceCut("Body", -1, 0,0,0,0,0,0, 0,0,0,0),
            "unbounded fitting removal accepted");
        check(RV.nativeSurfaceCutsActive(), "rejected fitting cut discarded committed state");
        var roofSelection=Class.forName("me.lens.rv.NativeRoof").getDeclaredMethod("selected",String.class,String.class,boolean.class);
        roofSelection.setAccessible(true);
        check(((java.util.List<?>)roofSelection.invoke(null,"RenamedModel","vehicles/body",true)).size()==1,
            "qualified FBX leaf skipped when actual model script has a different name");
        check(((java.util.List<?>)roofSelection.invoke(null,"RenamedModel","vehicles\\body",true)).size()==1,
            "Windows mesh path skipped qualified FBX leaf");
        check(((java.util.List<?>)roofSelection.invoke(null,"RenamedModel","body",true)).size()==1,
            "bare multi-mesh FBX object alias stopped matching");
        check(((java.util.List<?>)roofSelection.invoke(null,"RenamedModel","vehicles/otherbody",true)).isEmpty(),
            "unrelated mesh received fitting cut");
        check(((java.util.List<?>)roofSelection.invoke(null,"Body","vehicles/body",false)).isEmpty(),
            "fitting cut active outside occupied native vehicle");
        RV.setCutaway(null, 0,0,-1,10);
        RV.setNativeBodyWalls(true);
        check(!RV.nativeSurfaceCutsActive(), "fitting removal leaked between vehicles");
        RV.clearNativeSurfaceCuts();
        check(!RV.setNativeNearFace("Body",0,0,0,1,1,1,.3,.2,.4,.5), "side classifier crossed the body centre");
        check(!RV.setNativeNearFace("Body",1,0,0,2,1,1,0,0,0,0), "side classifier accepted missing UV authority");
        check(RV.setNativeNearFace("Body,mesh:body",1,0,0,2,1,1,.3,.2,.4,.5), "qualified side classifier rejected");
        var selectedNear=(java.util.List<?>)roofSelection.invoke(null,"Body","body",true);
        check(selectedNear.size()==1,"side classifier lost exact alias");
        var nearFlag=selectedNear.get(0).getClass().getDeclaredMethod("nearFace");
        nearFlag.setAccessible(true);
        check((boolean)nearFlag.invoke(selectedNear.get(0)),"side classifier became an unconditional surface removal");
        RV.setCutaway(null,0,0,-1,10);
        check(((java.util.List<?>)roofSelection.invoke(null,"Body","body",true)).isEmpty(),"side classifier survived vehicle change");
        RV.setNativeNearFace("Body",-2,0,0,-1,1,1,.3,.2,.4,.5);
        RV.clearCutaway();
        check(((java.util.List<?>)roofSelection.invoke(null,"Body","body",true)).isEmpty(),"side classifier survived exit");
        RV.setNativeBodyWalls(true);
        check(RV.setNativeEntryOpening(1, 2, 3, -1, -2, -3), "measured entry rejected reversed coordinates");
        check(RV.nativeEntryOpeningActive(), "native entry did not become active");
        var entryBounds = RV.class.getDeclaredField("nativeEntry");
        var nearBounds = RV.class.getDeclaredField("nativeEntryNear");
        entryBounds.setAccessible(true); nearBounds.setAccessible(true);
        Object committedAperture = entryBounds.get(null);
        check(RV.setNativeEntryNearBounds(-2,-3,-4,2,3,4), "rear thickness bounds rejected");
        check(entryBounds.get(null).equals(committedAperture), "rear thickness enlarged the usable aperture");
        RV.setCutaway(null, 0, 0, -1, 10);
        RV.setNativeBodyWalls(true);
        check(!RV.nativeEntryOpeningActive(), "entry aperture leaked to next vehicle");
        Object clearedNear = nearBounds.get(null);
        RV.setNativeEntryNearBounds(-2,-3,-4,2,3,4);
        RV.clearCutaway();
        check(nearBounds.get(null).equals(clearedNear), "rear thickness classifier survived exit");
        check(!RV.setNativeEntryNearBounds(Double.NaN,0,0,1,1,1), "invalid rear thickness accepted");
        RV.setNativeEntryOpening(-1, -2, -3, 1, 2, 3);
        RV.clearCutaway();
        RV.setNativeBodyWalls(true);
        check(!RV.nativeEntryOpeningActive(), "entry aperture survived clear");
        check(!RV.setNativeEntryOpening(Double.NaN, -2, -3, 1, 2, 3), "nonfinite entry accepted");
        check(!RV.nativeEntryOpeningActive(), "invalid entry retained a clipping region");
        var doorOpenings = RV.class.getDeclaredField("nativeDoorOpenings");
        doorOpenings.setAccessible(true);
        check(RV.setNativeDoorOpening("DoorMiddleLeft", 1, 2, 3, -1, -2, -3), "measured side aperture rejected");
        check(RV.setNativeDoorOpening("DoorMiddleLeft", 2, 3, 4, -2, -3, -4), "side aperture replacement rejected");
        check(((java.util.List<?>) doorOpenings.get(null)).size() == 1, "side aperture replacement appended duplicate");
        check(!RV.setNativeDoorOpening("DoorMiddleLeft", Double.POSITIVE_INFINITY, 0, 0, 1, 1, 1), "invalid side aperture accepted");
        check(((java.util.List<?>) doorOpenings.get(null)).isEmpty(), "invalid replacement left stale clipping");
        for (int i = 0; i < 4; i++) check(RV.setNativeDoorOpening("Door" + i, 0, 0, 0, 1, 1, 1), "bounded side aperture rejected");
        check(!RV.setNativeDoorOpening("Door4", 0, 0, 0, 1, 1, 1), "side apertures exceeded shader capacity");
        RV.setCutaway(null, 0, 0, -1, 10);
        check(((java.util.List<?>) doorOpenings.get(null)).isEmpty(), "side aperture leaked to next vehicle");
        RV.setNativeDoorOpening("DoorMiddleRight", 0, 0, 0, 1, 1, 1);
        RV.clearCutaway();
        check(((java.util.List<?>) doorOpenings.get(null)).isEmpty(), "side aperture survived exit");
        RV.clearCutaway();
        assertions++;
        final String arch = "-3,1;-2,0;-1,1";
        check(RV.setFlatWheelArch(arch, 1.062, .5), "valid arch rejected");
        check(!RV.flatWheelArchActive(), "flat arch active without native walls");
        RV.setNativeArchTrimModels("RearFenderLeft,RearFenderRight");
        check(!RV.nativeArchTrimActive(), "rear fitting trim active outside native mode");
        RV.setNativeBodyWalls(true);
        check(RV.flatWheelArchActive(), "native arch opt-in ignored");
        check(RV.nativeArchTrimActive(), "qualified rear fitting trim inactive");
        RV.setNativeArchTrimModels("");
        check(!RV.nativeArchTrimActive(), "empty rear fitting registry retained trim");
        RV.setNativeArchTrimModels("RearFenderLeft");
        var centre = Class.forName("me.lens.rv.FlatWheels").getDeclaredMethod("rearWheelCentre", org.joml.Matrix4f.class);
        centre.setAccessible(true);
        check((boolean)centre.invoke(null,new org.joml.Matrix4f().translation(2,-2,3)),
                "procedural rear wheel without mesh bounds skipped");
        check(!(boolean)centre.invoke(null,new org.joml.Matrix4f().translation(2,2,3)),
                "procedural front wheel receives rear arch mask");
        check(!(boolean)centre.invoke(null,new org.joml.Matrix4f().translation(2,-5,3)),
                "wheel centre outside measured arch receives mask");
        check(!(boolean)centre.invoke(null,new org.joml.Matrix4f().translation(Float.NaN,-2,3)),
                "nonfinite wheel transform accepted");
        RV.clearFlatWheelArch();
        check(!RV.nativeArchTrimActive(), "rear fitting trim survived cleared arch");
        check(!(boolean)centre.invoke(null,new org.joml.Matrix4f().translation(2,-2,3)),
                "cleared vehicle retains procedural wheel mask");
        RV.setFlatWheelArch(arch, 1.062, .5);
        var shaderError = Class.forName("me.lens.rv.Cutaway").getDeclaredField("shaderError");
        shaderError.setAccessible(true);
        shaderError.set(null, "deliberate failed shader fixture");
        check(!RV.flatWheelArchActive(), "failed shader did not restore physical-cover fallback");
        check(!RV.nativeArchTrimActive(), "rear fitting trim remained active with failed shader");
        shaderError.set(null, null);
        check(RV.flatWheelArchActive(), "cleared shader error retained inactive arch");
        for (String bad : new String[]{null, "", "1,2", "1,2;1,3", "2,1;1,2",
                "1,NaN;2,3", "1,2;Infinity,3", "1,2;2,3;", "1,2,3;2,3"}) {
            check(!RV.setFlatWheelArch(bad, 1.062, .5), "invalid contour accepted: " + bad);
            check(!RV.flatWheelArchActive(), "invalid contour left stale active arch");
            RV.setFlatWheelArch(arch, 1.062, .5);
        }
        StringBuilder limit = new StringBuilder();
        for (int i=0; i<16; i++) { if (i>0) limit.append(';'); limit.append(i).append(",1"); }
        check(RV.setFlatWheelArch(limit.toString(), 1, 0), "16-point contour rejected");
        check(!RV.setFlatWheelArch(limit + ";16,1", 1, 0), "17-point contour accepted");
        for (double bad : new double[]{0, -1, Double.NaN, Double.POSITIVE_INFINITY, Double.MAX_VALUE, Double.MIN_VALUE}) {
            RV.setFlatWheelArch(arch, 1.062, .5);
            check(!RV.setFlatWheelArch(arch, bad, .5) && !RV.flatWheelArchActive(), "invalid width retained active arch");
        }
        for (double bad : new double[]{Double.NaN, Double.NEGATIVE_INFINITY, Double.MAX_VALUE}) {
            RV.setFlatWheelArch(arch, 1.062, .5);
            check(!RV.setFlatWheelArch(arch, 1, bad) && !RV.flatWheelArchActive(), "invalid floor retained active arch");
        }
        RV.setFlatWheelArch(arch, 1.062, .5);
        RV.clearFlatWheelArch();
        check(!RV.flatWheelArchActive(), "explicit arch clear retained active contour");
        RV.setFlatWheelArch(arch, 1.062, .5);
        RV.setCutaway(null, 0, 0, -1, 10);
        RV.setNativeBodyWalls(true);
        check(!RV.flatWheelArchActive(), "new vehicle retained previous arch");
        RV.setFlatWheelArch(arch, 1.062, .5);
        RV.clearCutaway();
        RV.setNativeBodyWalls(true);
        check(!RV.flatWheelArchActive(), "cleared vehicle retained previous arch");
        final String leftCurve="0,11,-2;1,9,-2.5;2,11,-2.1";
        final String rightCurve="0,11,2.2;.8,8,2.6;2,11,2.3";
        check(RV.setCurvedWheelArches(leftCurve,rightCurve,10), "asymmetric curved arches rejected");
        check(RV.flatWheelArchActive(), "curved arch did not use shared native activation");
        for(String bad:new String[]{null,"","0,11,-2", "0,11,-2;0,11,-2.1",
                "0,11,2;2,11,2", "0,11,-2;2,NaN,-2", "0,9,-2;2,11,-2"}) {
            check(!RV.setCurvedWheelArches(bad,rightCurve,10),"invalid bilateral side accepted: "+bad);
            check(!RV.flatWheelArchActive(),"invalid curved side retained stale active arch");
        }
        check(!RV.setCurvedWheelArches(leftCurve,rightCurve,Double.NaN),"nonfinite curved floor accepted");
        RV.setCurvedWheelArches(leftCurve,rightCurve,10);
        RV.setCutaway(null,0,0,-1,10);
        RV.setNativeBodyWalls(true);
        check(!RV.flatWheelArchActive(),"curved profiles leaked into the next vehicle");
        RV.setFlatWheelArch(arch,3,10);
        final String stockLeft="-3,-2,9,8,2;-1.8,-1,7,8,2.2";
        final String stockRight="-3,-1,8,9,2.3";
        check(RV.setNativeWheelWellTrim(stockLeft,stockRight,1,1.1),"stepped/disjoint stock well rejected");
        check(RV.nativeWheelWellTrimActive(),"stock well trim not armed with native body");
        for(String bad:new String[]{null,"","0,0,1,1,2","1,0,1,1,2","0,1,NaN,1,2",
                "0,1,1,1,.5","0,1,1,1,4","0,2,1,1,2;1,3,1,1,2","0,1,1,1,2;"}) {
            RV.setFlatWheelArch(arch,3,10);
            check(!RV.setNativeWheelWellTrim(bad,stockRight,1,1.1),"invalid stock well input accepted: "+bad);
            check(!RV.flatWheelArchActive() && !RV.nativeWheelWellTrimActive(),"rejected stock well left a flat floor without its trim");
        }
        RV.setFlatWheelArch(arch,3,10);RV.setNativeWheelWellTrim(stockLeft,stockRight,1,1.1);
        RV.setFlatWheelArch(arch,3,10);
        check(!RV.nativeWheelWellTrimActive(),"new arch retained old stock-well slabs");
        RV.setNativeWheelWellTrim(stockLeft,stockRight,1,1.1);
        RV.setCutaway(null,0,0,-1,10);RV.setNativeBodyWalls(true);
        check(!RV.nativeWheelWellTrimActive(),"stock trim leaked across vehicle change");
        RV.setFlatWheelArch(arch,3,10);RV.setNativeWheelWellTrim(stockLeft,stockRight,1,1.1);
        RV.clearCutaway();RV.setNativeBodyWalls(true);
        check(!RV.nativeWheelWellTrimActive(),"stock trim survived interior exit");
        RV.setNativeBodyWalls(false);
        var spareClassifier = Class.forName("me.lens.rv.Cutaway").getDeclaredMethod("exteriorSpare", String.class, String.class);
        spareClassifier.setAccessible(true);
        check(!(boolean) spareClassifier.invoke(null, "87fordB700spare0", "Roofrack"), "bus roof spare bypassed its removed roof cut");
        check(!(boolean) spareClassifier.invoke(null, "87fordB700spare1", "Roofrack"), "second bus roof spare bypassed its removed roof cut");
        check((boolean) spareClassifier.invoke(null, "KI5trailersSpare", "TruckBed"), "Scamp rear spare was clipped with the near wall");
        check((boolean) spareClassifier.invoke(null, "KI5trailersSpare0", "FrontArea"), "Bambi front spare was clipped with the cabin");
        check(!(boolean) spareClassifier.invoke(null, "unknownSpare", null), "unclassified spare bypassed cabin cuts");
        var doorClassifier = Class.forName("me.lens.rv.Cutaway").getDeclaredMethod("openingDoorId", String.class);
        doorClassifier.setAccessible(true);
        for (String id : new String[]{"DoorFrontRight", "DoorRear", "TrunkDoor"})
            check((boolean) doorClassifier.invoke(null, id), "physical opening lost native leaf treatment: "+id);
        for (String id : new String[]{"DAMNTrailerAwning", "DAMNVents", "DAMNTrailerJack"})
            check(!(boolean) doorClassifier.invoke(null, id), "accessory animation treated as a physical leaf: "+id);
        var restClassifier = Class.forName("me.lens.rv.Cutaway").getDeclaredMethod("restFinishModel", String.class);
        restClassifier.setAccessible(true);
        for (String name : new String[]{"86fordE150doorrl", "86fordE150doorrr", "86fordE150doorrlw", "86fordE150doorrrw", "86fordE150trunkDoor"})
            check((boolean) restClassifier.invoke(null, name), "qualified rigid leaf lost persistent finish: "+name);
        for (String name : new String[]{"87fordF700TrunkDoorX", "86fordE150doorfl", "86fordE150PanelLeft", "86fordE150doorrrwa", "61shastaCamperDoorfr", "unknown", null})
            check(!(boolean) restClassifier.invoke(null, name), "unqualified rest frame accepted: "+name);
        var glassClassifier = Class.forName("me.lens.rv.Cutaway").getDeclaredMethod("glazingPartId", String.class);
        glassClassifier.setAccessible(true);
        for (String id : new String[]{"WindshieldRear", "Windshield", "WindowBackLeft"})
            check((boolean) glassClassifier.invoke(null, id), "native fixed glazing was omitted: "+id);
        for (String id : new String[]{"WindshieldRearArmor", "DAMNBackLeftArmor", "GloveBox"})
            check(!(boolean) glassClassifier.invoke(null, id), "non-glazing restored as a pane: "+id);
        RV.setBodyLining(.8, .76, .66);
        for (int mode : new int[]{5, 6, 7, 14, 15, 22, 0}) {
            RV.setBodyLiningDebugMode(mode);
            check(RV.bodyLiningDebugMode() == mode, "surface diagnostic mode ignored");
        }
        for (double invalid : new double[]{-1, .5, 23, Double.NaN, Double.POSITIVE_INFINITY}) {
            RV.setBodyLiningDebugMode(6);
            RV.setBodyLiningDebugMode(invalid);
            check(RV.bodyLiningDebugMode() == 0, "invalid surface diagnostic mode retained stale data");
        }
        RV.setBodyLiningDebugMode(6);
        RV.setCutaway(null, 0, 0, -1, 10);
        check(RV.bodyLiningDebugMode() == 0, "surface diagnostic leaked between vehicles");
        RV.setBodyLining(.8, .76, .66);
        RV.setBodyLiningDebugMode(6);
        RV.clearCutaway();
        check(RV.bodyLiningDebugMode() == 0, "surface diagnostic survived exit");
        RV.setNativeBodyWalls(false);
        check(RV.setNativeBodyTrim(1, 2, 3, 4, 5, 6, .539, .096, .997, .999), "measured hitch trim rejected");
        check(!RV.nativeBodyTrimActive(), "hitch trim active outside native mode");
        RV.setNativeBodyWalls(true);
        check(RV.nativeBodyTrimActive(), "native hitch trim ignored");
        for (double[] uv : new double[][]{{-.01, 0, 1, 1}, {0, 0, 1.01, 1}, {.9, 0, .8, 1},
                {0, .5, 1, .5}, {Double.NaN, 0, 1, 1}, {0, 0, 1, Double.POSITIVE_INFINITY},
                {Double.MIN_VALUE, 0, Double.MIN_VALUE * 2, 1}}) {
            RV.setNativeBodyTrim(1, 2, 3, 4, 5, 6, .539, .096, .997, .999);
            check(!RV.setNativeBodyTrim(1, 2, 3, 4, 5, 6, uv[0], uv[1], uv[2], uv[3]), "invalid hitch UV accepted");
            check(!RV.nativeBodyTrimActive(), "invalid hitch UV left stale clipping");
        }
        check(!RV.setNativeBodyTrim(1, 2, 3, Double.NaN, 5, 6, 0, 0, 1, 1), "invalid hitch box accepted");
        check(!RV.setNativeBodyTrim(1, 2, 3, 1, 5, 6, 0, 0, 1, 1), "empty hitch box accepted");
        RV.setNativeBodyTrim(1, 2, 3, 4, 5, 6, .539, .096, .997, .999);
        RV.setCutaway(null, 0, 0, -1, 10);
        RV.setNativeBodyWalls(true);
        check(!RV.nativeBodyTrimActive(), "hitch trim leaked between vehicles");
        RV.setNativeBodyTrim(1, 2, 3, 4, 5, 6, .539, .096, .997, .999);
        RV.clearCutaway();
        RV.setNativeBodyWalls(true);
        check(!RV.nativeBodyTrimActive(), "hitch trim survived exit");
        RV.setNativeBodyTrim(1, 2, 3, 4, 5, 6, .539, .096, .997, .999);
        RV.clearNativeBodyTrim();
        check(!RV.nativeBodyTrimActive(), "explicit hitch trim clear ignored");
        RV.setNativeBodyWalls(false);
        System.out.println("Cutaway state assertions=" + assertions + " productionJava=true nativeInput=false renderAcceptance=false");
    }
}
