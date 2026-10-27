package me.lens.rv;

import java.util.ArrayList;
import java.util.List;
import java.util.Set;
import zombie.core.opengl.ShaderProgram;

/** Shared measured native cuts: roof remnants and embedded replacement furniture.
 * Joint model/position/UV predicates retain the surrounding hull and glazing. */
final class NativeRoof {
    record UV(float minU, float minV, float maxU, float maxV) {
        boolean present() { return minU < maxU && minV < maxV; }
    }
    record Cut(Set<String> models, float maxUp, RV.NativeEntry bounds, UV uv, boolean nearFace) { }
    static volatile List<Cut> cuts = List.of();
    static final int MAX_DRAW_CUTS = 4;

    private NativeRoof() { }

    static boolean add(String names, double maxUp, double ax, double ay, double az,
            double bx, double by, double bz, double minU, double minV, double maxU, double maxV) {
        return add(names,maxUp,ax,ay,az,bx,by,bz,minU,minV,maxU,maxV,false);
    }

    static boolean addNear(String names, double ax, double ay, double az,
            double bx, double by, double bz, double minU, double minV, double maxU, double maxV) {
        return add(names,-1,ax,ay,az,bx,by,bz,minU,minV,maxU,maxV,true);
    }

    private static boolean add(String names, double maxUp, double ax, double ay, double az,
            double bx, double by, double bz, double minU, double minV, double maxU, double maxV, boolean nearFace) {
        if (names == null || names.isBlank() || cuts.size() >= 16
                || !Double.isFinite(maxUp) || !(maxUp == -1 || maxUp >= 0 && maxUp <= 1)) return false;
        Set<String> models = Set.copyOf(java.util.Arrays.asList(names.split(",")));
        if (models.stream().anyMatch(name -> !name.matches("[A-Za-z0-9_:.]+"))) return false;
        for (double value : new double[]{ax, ay, az, bx, by, bz})
            if (!Double.isFinite(value) || Math.abs(value) > 10000) return false;
        for (double value : new double[]{minU, minV, maxU, maxV})
            if (!Double.isFinite(value) || value < 0 || value > 1) return false;
        RV.NativeEntry bounds = new RV.NativeEntry((float)Math.min(ax,bx), (float)Math.min(ay,by), (float)Math.min(az,bz),
            (float)Math.max(ax,bx), (float)Math.max(ay,by), (float)Math.max(az,bz));
        boolean noBounds = ax == 0 && ay == 0 && az == 0 && bx == 0 && by == 0 && bz == 0;
        UV uv = new UV((float)minU, (float)minV, (float)maxU, (float)maxV);
        boolean noUV = minU == 0 && minV == 0 && maxU == 0 && maxV == 0;
        if (!noBounds && !bounds.present() || !noUV && !uv.present() || maxUp == -1 && noBounds && noUV) return false;
        // A side-edge classifier always needs joint source bounds and UVs on
        // one physical side. It never defines or enlarges an opening.
        if (nearFace && (noBounds || noUV || bounds.minX()*bounds.maxX() <= 0)) return false;
        Cut next = new Cut(models, (float)maxUp, bounds, uv, nearFace);
        var updated = new ArrayList<>(cuts);
        updated.add(next);
        var aliases = new java.util.HashSet<String>();
        updated.forEach(cut -> aliases.addAll(cut.models()));
        var modelNames = new java.util.HashSet<String>();
        var meshNames = new java.util.HashSet<String>();
        modelNames.add(""); meshNames.add("");
        aliases.forEach(alias -> (alias.startsWith("mesh:") ? meshNames : modelNames).add(alias));
        // A draw can match its script name and its mesh alias together. Validate
        // their union rather than limiting unrelated model rules to four total.
        for (String model : modelNames) for (String mesh : meshNames)
            if (updated.stream().filter(cut -> cut.models().contains(model) || cut.models().contains(mesh)).count()
                    > MAX_DRAW_CUTS) return false;
        cuts = List.copyOf(updated);
        return true;
    }

    static List<Cut> selected(String name, String mesh, boolean active) {
        // A single-mesh FBX is reported as vehicles/Vehicles_VanAmbulance;
        // an object selected from a multi-mesh file is already a bare name.
        // Both must match the source-qualified object alias, including when
        // its model script has a different name (Vehicles_Ambulance).
        int slash=Math.max(mesh.lastIndexOf('/'),mesh.lastIndexOf('\\'));
        String leaf=mesh.substring(slash+1);
        return active ? cuts.stream().filter(cut -> cut.models().contains(name)
            || cut.models().contains("mesh:" + leaf)).toList() : List.of();
    }

    static void upload(ShaderProgram program, String name, String mesh, boolean active) {
        List<Cut> selected = selected(name,mesh,active);
        for (int i=0; i<MAX_DRAW_CUTS; i++) {
            Cut cut = i < selected.size() ? selected.get(i) : null;
            program.setVector4("MELensRoofCut"+i, cut == null ? -1 : cut.maxUp(),
                cut != null && cut.bounds().present() ? 1 : 0, cut != null && cut.uv().present() ? 1 : 0,
                cut == null ? 0 : !cut.nearFace() ? 1 : cut.bounds().minX()+cut.bounds().maxX() > 0 ? 3 : 2);
            if (cut == null) continue;
            RV.NativeEntry box = cut.bounds();
            program.setVector3("MELensRoofMin"+i, box.minX(), box.minY(), box.minZ());
            program.setVector3("MELensRoofMax"+i, box.maxX(), box.maxY(), box.maxZ());
            UV uv = cut.uv();
            program.setVector4("MELensRoofUV"+i, uv.minU(), uv.minV(), uv.maxU(), uv.maxV());
        }
    }
}
