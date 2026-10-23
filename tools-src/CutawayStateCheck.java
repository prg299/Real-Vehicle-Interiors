import me.lens.rv.RV;

/** Production state contract only; no renderer, native input or engine doubles. */
public final class CutawayStateCheck {
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
        System.out.println("Cutaway state assertions=4 productionJava=true nativeInput=false renderAcceptance=false");
    }
}
