import java.lang.reflect.Field;
import me.lens.rv.ViewpointCompat;
import zombie.characters.IsoGameCharacter;

/** Tests the optional camera-state contract, not Viewpoint rendering or native input. */
public final class ViewpointCompatCheck {
    private static int assertions;

    private static void check(boolean condition, String message) {
        assertions++;
        if (!condition) throw new AssertionError(message);
    }

    public static void main(String[] args) throws Exception {
        String scenario = args[0];
        IsoGameCharacter player = new IsoGameCharacter();
        if (scenario.equals("missing") || scenario.equals("changed-api")) {
            check(!ViewpointCompat.active(), "Optional camera API must not disable normal rendering");
            check(!ViewpointCompat.active(), "Repeated optional API lookup changed the result");
            check(!ViewpointCompat.useIsometric(player), "Absent/changed API must be a no-op");
        } else if (scenario.equals("toggle") || scenario.equals("missing-switch")) {
            Class<?> camera = Class.forName("viewpoint.core.View");
            Field enabled = camera.getField("enabled");
            Field thirdPerson = camera.getField("thirdPerson");
            check(!ViewpointCompat.active(), "Installed Viewpoint must not disable isometric rendering");
            check(!ViewpointCompat.useIsometric(player), "Already isometric must not transition");
            for (int i = 0; i < 3; i++) {
                thirdPerson.setBoolean(null, false);
                enabled.setBoolean(null, true);
                check(ViewpointCompat.active(), "First-person camera was not detected");
                thirdPerson.setBoolean(null, true);
                check(ViewpointCompat.active(), "Third-person camera was not detected");
                enabled.setBoolean(null, false);
                check(!ViewpointCompat.active(), "Isometric rendering did not resume");
            }
            if (scenario.equals("missing-switch")) {
                enabled.setBoolean(null, true);
                check(!ViewpointCompat.useIsometric(player), "Missing transition API must be a no-op");
                check(ViewpointCompat.active(), "Missing transition API must not corrupt camera state");
            } else {
                Class<?> fp = Class.forName("viewpoint.FP");
                Field calls = fp.getField("calls");
                for (boolean third : new boolean[]{false, true}) {
                    thirdPerson.setBoolean(null, third);
                    enabled.setBoolean(null, true);
                    int before = calls.getInt(null);
                    check(!ViewpointCompat.useIsometric(null), "Null player must not change camera");
                    check(ViewpointCompat.useIsometric(player), "Interior handoff did not switch to isometric");
                    check(!ViewpointCompat.active(), "Perspective view still active inside");
                    check(calls.getInt(null) == before + 1, "Must call Viewpoint's own transition exactly once");
                    check(fp.getField("actor").get(null) == player, "Wrong camera character");
                    check(!ViewpointCompat.useIsometric(player), "Repeated tick must not reset camera caches");
                    check(calls.getInt(null) == before + 1, "Unchanged tick repeated the transition");
                    enabled.setBoolean(null, true);
                    check(ViewpointCompat.active(), "Viewpoint cannot be re-enabled after leaving");
                    enabled.setBoolean(null, false);
                }
            }
        } else {
            throw new IllegalArgumentException("Unknown scenario: " + scenario);
        }
        System.out.println("Viewpoint camera contract: " + scenario + " assertions=" + assertions
                + " optionalApiDouble=true nativeInput=false renderAcceptance=false");
    }
}
