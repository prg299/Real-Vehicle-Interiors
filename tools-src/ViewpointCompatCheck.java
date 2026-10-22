import java.lang.reflect.Field;
import me.lens.rv.ViewpointCompat;

/** Tests the optional camera-state contract, not Viewpoint rendering or native input. */
public final class ViewpointCompatCheck {
    private static int assertions;

    private static void check(boolean condition, String message) {
        assertions++;
        if (!condition) throw new AssertionError(message);
    }

    public static void main(String[] args) throws Exception {
        String scenario = args[0];
        if (scenario.equals("missing") || scenario.equals("changed-api")) {
            check(!ViewpointCompat.active(), "Optional camera API must not disable normal rendering");
            check(!ViewpointCompat.active(), "Repeated optional API lookup changed the result");
        } else if (scenario.equals("toggle")) {
            Class<?> camera = Class.forName("viewpoint.core.View");
            Field enabled = camera.getField("enabled");
            Field thirdPerson = camera.getField("thirdPerson");
            check(!ViewpointCompat.active(), "Installed Viewpoint must not disable isometric rendering");
            for (int i = 0; i < 3; i++) {
                thirdPerson.setBoolean(null, false);
                enabled.setBoolean(null, true);
                check(ViewpointCompat.active(), "First-person camera was not detected");
                thirdPerson.setBoolean(null, true);
                check(ViewpointCompat.active(), "Third-person camera was not detected");
                enabled.setBoolean(null, false);
                check(!ViewpointCompat.active(), "Isometric rendering did not resume");
            }
        } else {
            throw new IllegalArgumentException("Unknown scenario: " + scenario);
        }
        System.out.println("Viewpoint camera contract: " + scenario + " assertions=" + assertions
                + " optionalApiDouble=true nativeInput=false renderAcceptance=false");
    }
}
