package me.lens.rv;

import java.util.List;

/** Production geometry/registration checks; native zombie behavior is tested separately. */
public final class VisionStateCheck {
    private static int assertions;
    private static void check(boolean value, String message) {
        assertions++;
        if (!value) throw new AssertionError(message);
    }
    public static void main(String[] args) throws Exception {
        var hull = new Vision.Hull(new float[] {-1,-3, 1,-3, 1,3, -1,3}, List.of());
        for (float[] outside : new float[][] {{-5,0},{5,0},{0,5},{0,-5},{5,5},{-5,-5}}) {
            check(hull.blocks(null, 0,0, outside[0],outside[1]), "closed wall failed");
        }
        check(!hull.blocks(null, 0,0,.5f,2), "same-room observer blocked");
        check(!hull.blocks(null, 4,0,5,0), "outside target blocked");
        var side = new Vision.Opening("Window", false, 1,1.1f,-.5f,.5f);
        check(side.intersection(0,0,5,0) > 0, "side window ray missed");
        check(side.intersection(0,2,5,0) < 0, "solid section treated as glass");
        check(side.intersection(0,0,0,5) < 0, "front/rear ray crossed side window");
        check(side.intersection(2,0,3,0) < 0, "opening behind ray origin matched");
        var cab = new Vision.Hull(hull.ring(), List.of(new Vision.Opening("Windshield", false, -.7f,.7f,5,5.1f)));
        check(cab.blocks(null,0,0,0,10), "distant cab glass opened a solid cargo partition");
        var strip = new Vision.Hull(hull.ring(), List.of(side));
        check(strip.blocks(null,0,2,5,2), "window beside ray opened an opaque wall section");
        var area = new Vision.Opening("WindowMiddleLeft", false, .84f,1.7f,-.55f,.31f);
        float at = area.intersection(0,-.2f,5,0,.639f/5);
        check(at > .16f && at < .17f, "wide stock interaction area measured from its midpoint");
        check(Math.abs(at*5-.639f)<.2f, "near edge of stock window treated as a distant cab opening");
        check(area.facesWall(0,2) && !area.facesWall(2,0), "side glass opened a perpendicular cargo divider");
        var windshield = new Vision.Opening("Windshield",false,-1,1,3,3.1f);
        check(windshield.facesWall(2,0) && !windshield.facesWall(0,2), "windshield opened the side wall");
        Vision.register("test.hull", "-1,-3;1,-3;1,3;-1,3", "Window,window,1,1.1,-.5,.5");
        var field = Vision.class.getDeclaredField("HULLS"); field.setAccessible(true);
        var map = (java.util.Map<?,?>)field.get(null);
        Object original = map.get("test.hull");
        check(original != null, "complete metadata not published");
        for (String bad : new String[] {"Window,unknown,0,1,0,1", "Window,door,NaN,1,0,1", "Window,door,2,1,0,1"}) {
            boolean rejected = false;
            try { Vision.register("test.hull", "-1,-3;1,-3;1,3;-1,3", bad); }
            catch (IllegalArgumentException expected) { rejected = true; }
            check(rejected && map.get("test.hull") == original, "invalid update damaged committed hull");
        }
        System.out.println("Vision geometry assertions=" + assertions + " productionJava=true nativeBehavior=false");
    }
}
