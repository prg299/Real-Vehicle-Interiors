package me.lens.rv;

import java.util.Map;
import java.util.concurrent.ConcurrentHashMap;
import org.lwjgl.opengl.GL11;
import org.lwjgl.opengl.GL13;
import zombie.core.opengl.ShaderProgram;
import zombie.core.skinnedmodel.model.VehicleModelInstance;
import zombie.core.skinnedmodel.shader.Shader;
import zombie.core.textures.Texture;

/** Reuses the existing lining atlas on the dependency's curved structural skin. */
final class NativeFinish {
    record Material(String texture, float scale, float height, float perimeter, boolean boundary) {
        static final Material NONE = new Material("", 0, 0, 0, false);
    }
    static volatile Material material = Material.NONE;
    record StockMetal(String texture, float scale, float paintU, float paintV,
            float u0, float v0, float u1, float v1, float width, float height) {
        static final StockMetal NONE = new StockMetal("",0,0,0,0,0,0,0,0,0);
    }
    static volatile StockMetal stockMetal = StockMetal.NONE;
    private static final Map<String, Texture> textures = new ConcurrentHashMap<>();
    // Native vehicle inputs occupy units 0..10. Keep our extra input scoped to
    // the single model draw, including the previous binding and active unit.
    private static final int UNIT = GL13.GL_TEXTURE15;
    private static final ThreadLocal<Integer> previousBinding = new ThreadLocal<>();
    private static final ThreadLocal<int[]> stockBindings = new ThreadLocal<>();

    private NativeFinish() {}

    static boolean set(String texture, double scale, double height, double perimeter) {
        material = Material.NONE;
        stockMetal = StockMetal.NONE;
        if (texture == null || !texture.matches("MELensShell_[a-z0-9_]+_walls")
                || !Double.isFinite(scale) || !Double.isFinite(height) || !Double.isFinite(perimeter)
                || scale <= 0 || scale > 1 || height < .5 || height > 4 || perimeter < 2 || perimeter > 40) return false;
        material = new Material(texture, (float) scale, (float) height, (float) perimeter, false);
        return true;
    }

    /** Source-qualified game texture references; no copied or generated vehicle artwork. */
    static boolean setStock(String texture, double scale, double paintU, double paintV,
            double u0, double v0, double u1, double v1, double width, double height) {
        stockMetal = StockMetal.NONE;
        double[] values = {scale,paintU,paintV,u0,v0,u1,v1,width,height};
        for (double value : values) if (!Double.isFinite(value)) return false;
        if (texture == null || !texture.matches("vehicle_[a-z0-9_]+")
                || material == Material.NONE || !RV.bodyLining.plain()
                || scale <= 0 || scale > 1 || Math.abs(scale-material.scale()) > .000001
                || paintU < 0 || paintU > 1 || paintV < 0 || paintV > 1
                || u0 < 0 || v0 < 0 || u1 > 1 || v1 > 1 || u0 >= u1 || v0 >= v1
                || width < .2 || width > 4 || height < .2 || height > 4) return false;
        stockMetal = new StockMetal(texture,(float)scale,(float)paintU,(float)paintV,
                (float)u0,(float)v0,(float)u1,(float)v1,(float)width,(float)height);
        return true;
    }

    static boolean stockActive() { return stockMetal != StockMetal.NONE; }

    /** Bind the live skin and the neutral pressed panel only for one eligible structural draw. */
    static void uploadStock(ShaderProgram program, boolean eligible, VehicleModelInstance root, Shader source) {
        StockMetal selected = stockMetal;
        program.setVector4("MELensStockMetal",0,0,0,0);
        if (!eligible || !RV.roomEnabled || selected == StockMetal.NONE || root == null || source == null
                || !source.isVehicleShader() || RV.roomRing.length < 6
                || root.tex == null || !root.tex.isReady()) return;
        Texture panel = textures.computeIfAbsent(selected.texture(),
                key -> Texture.getSharedTexture("media/textures/Vehicles/"+key+".png"));
        if (panel == null || !panel.isReady()) return;
        int active = GL11.glGetInteger(GL13.GL_ACTIVE_TEXTURE);
        int[] prior = new int[2];
        // Preserve both bindings before any texture setter can change an active unit.
        for (int i=0;i<2;i++) {
            GL13.glActiveTexture(GL13.GL_TEXTURE13+i);
            prior[i]=GL11.glGetInteger(GL11.GL_TEXTURE_BINDING_2D);
        }
        stockBindings.set(prior);
        try {
            GL13.glActiveTexture(GL13.GL_TEXTURE13);
            program.setValue("MELensStockPaintTexture",root.tex,13);
            GL13.glActiveTexture(GL13.GL_TEXTURE13);
            GL11.glBindTexture(GL11.GL_TEXTURE_2D,root.tex.getID());
            GL13.glActiveTexture(GL13.GL_TEXTURE14);
            program.setValue("MELensStockPanelTexture",panel,14);
            GL13.glActiveTexture(GL13.GL_TEXTURE14);
            GL11.glBindTexture(GL11.GL_TEXTURE_2D,panel.getID());
        } finally { GL13.glActiveTexture(active); }
        program.setVector4("MELensStockMetal",selected.scale(),selected.width(),selected.height(),1);
        program.setVector4("MELensStockPaint",selected.paintU(),selected.paintV(),
                "vehicle_multiuv".equals(source.getName()) ? 1f : 0f,0);
        program.setVector4("MELensStockPanel",selected.u0(),selected.v0(),selected.u1(),selected.v1());
        program.setVector4("MELensStockHSV",root.painColor.x,root.painColor.y,root.painColor.z,0);
        float[] ring=RV.roomRing;
        float maxX=Float.NEGATIVE_INFINITY,minZ=Float.POSITIVE_INFINITY;
        for (int i=0;i+1<ring.length;i+=2) { maxX=Math.max(maxX,ring[i]); minZ=Math.min(minZ,ring[i+1]); }
        program.setVector4("MELensStockOrigin",-maxX*selected.scale(),minZ*selected.scale(),RV.roomFloorDot,0);
    }

    static void setBoundary(boolean enabled) {
        Material current = material;
        if (current != Material.NONE)
            material = new Material(current.texture(), current.scale(), current.height(), current.perimeter(), enabled);
    }

    static void upload(ShaderProgram program, boolean body) {
        Material selected = material;
        Texture texture = !body || selected == Material.NONE ? null : textures.computeIfAbsent(selected.texture(),
                key -> Texture.getSharedTexture("media/textures/Vehicles/" + key + ".png"));
        if (texture == null) {
            // Coordinates remain meaningful on untextured native leaves in
            // diagnostic mode. The zero enable flag keeps their finish native.
            program.setVector4("MELensWallMaterial", selected.scale(), selected.height(), selected.perimeter(), 0);
            return;
        }
        int active = GL11.glGetInteger(GL13.GL_ACTIVE_TEXTURE);
        GL13.glActiveTexture(UNIT);
        previousBinding.set(GL11.glGetInteger(GL11.GL_TEXTURE_BINDING_2D));
        program.setValue("MELensWallTexture", texture, 15);
        GL13.glActiveTexture(UNIT);
        // Texture.bind's unit-zero cache may already name this atlas after a
        // support draw. Unit 15 still needs its own explicit binding.
        GL11.glBindTexture(GL11.GL_TEXTURE_2D, texture.getID());
        GL13.glActiveTexture(active);
        program.setVector4("MELensWallMaterial", selected.scale(), selected.height(), selected.perimeter(), selected.boundary() ? 2 : 1);
        float[] ring = RV.roomRing;
        float minX=Float.POSITIVE_INFINITY, minY=minX, maxX=-minX, maxY=-minX;
        for (int i=0; i+1<ring.length; i+=2) {
            minX=Math.min(minX,ring[i]); maxX=Math.max(maxX,ring[i]);
            minY=Math.min(minY,ring[i+1]); maxY=Math.max(maxY,ring[i+1]);
        }
        // The atlas belongs to the living compartment, never to its hitch,
        // propane bracket or the cab ahead of the measured partition.
        // Native wall sections bow beyond the floor ring: Scamp16 needs
        // .2371m at its nose; the bus rear leaf needs .1585m. A .25m envelope
        // includes those skins while ending before the camper hitch.
        float margin=.25f/selected.scale();
        program.setVector4("MELensWallMaterialBounds", minX-margin,minY-margin,maxX+margin,maxY+margin);
        // Passenger-space origin also drives the authored stock partition and
        // arch patches. One continuous projection avoids phase changes where
        // the native shell turns a corner or its stored normal changes.
        program.setVector4("MELensWallMaterialOrigin", -maxX*selected.scale(),minY*selected.scale(),0f,0f);
    }

    static void restore() {
        int[] stock = stockBindings.get();
        if (stock != null) {
            int active=GL11.glGetInteger(GL13.GL_ACTIVE_TEXTURE);
            for(int i=0;i<2;i++) {
                GL13.glActiveTexture(GL13.GL_TEXTURE13+i);
                GL11.glBindTexture(GL11.GL_TEXTURE_2D,stock[i]);
            }
            GL13.glActiveTexture(active);
            stockBindings.remove();
        }
        Integer binding = previousBinding.get();
        if (binding == null) return;
        int active = GL11.glGetInteger(GL13.GL_ACTIVE_TEXTURE);
        GL13.glActiveTexture(UNIT);
        GL11.glBindTexture(GL11.GL_TEXTURE_2D, binding);
        GL13.glActiveTexture(active);
        previousBinding.remove();
    }
}
