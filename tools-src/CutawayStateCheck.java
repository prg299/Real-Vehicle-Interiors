import me.lens.rv.RV;

/** Production state contract only; no renderer, native input or engine doubles. */
public final class CutawayStateCheck {
    private static int assertions = 4;

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
        RV.setCutFront(14);
        RV.setCutFrontTop(-12);
        if (height.getFloat(null) != -12f) throw new AssertionError("explicit cab height lost");
        RV.setCutFront(21);
        if (height.getFloat(null) != -1e9f) throw new AssertionError("previous vehicle cab height leaked");
        RV.setCutFrontTop(-45);
        if (height.getFloat(null) != -45f) throw new AssertionError("next vehicle cab height ignored");
        RV.clearCutFront();
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
        RV.setCutaway(null, 0, 0, -1, 10);
        if (lining.get(null) != none) throw new AssertionError("lining leaked to another vehicle");
        assertions++;
        RV.setBodyLining(Double.NaN, .57, .59);
        if (lining.get(null) != none) throw new AssertionError("invalid lining accepted");
        assertions++;
        RV.setBodyLining(.55, .57, .59);
        RV.setBodyLiningDebug(true);
        RV.clearCutaway();
        if (lining.get(null) != none) throw new AssertionError("clear retained diagnostic lining");
        assertions++;
        System.out.println("Cutaway state assertions=" + assertions + " productionJava=true nativeInput=false renderAcceptance=false");
    }
}
