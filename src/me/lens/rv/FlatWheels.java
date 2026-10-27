package me.lens.rv;

import java.util.concurrent.ConcurrentHashMap;
import java.util.concurrent.atomic.AtomicLong;
import org.joml.Matrix4f;
import org.joml.Vector3f;
import org.lwjgl.opengl.GL20;
import zombie.core.opengl.ShaderProgram;
import zombie.core.skinnedmodel.model.ModelMesh;

/** Reciprocal arch visibility for measured planar or bilateral curved profiles. No saved state. */
final class FlatWheels {
    private static final ConcurrentHashMap<Integer,Integer> locations = new ConcurrentHashMap<>();
    private static final ConcurrentHashMap<String,Integer> curveLocations = new ConcurrentHashMap<>();
    private static final Vector3f corner = new Vector3f();
    private static final AtomicLong wheels = new AtomicLong(), interiors = new AtomicLong();
    private static final AtomicLong fittings = new AtomicLong();
    private record StockTrim(int leftCount,int rightCount,float leftInner,float rightInner,
            float[] left,float[] right,float[] limits) {
        static final StockTrim NONE=new StockTrim(0,0,0,0,new float[128],new float[128],new float[64]);
    }
    private static volatile StockTrim stock=StockTrim.NONE;
    private static final AtomicLong stockDraws=new AtomicLong();

    private FlatWheels() {}

    static void clearStockTrim(){stock=StockTrim.NONE;}
    static boolean stockTrimActive(){return stock!=StockTrim.NONE;}

    /** Independent source roof slabs preserve steps and gaps in stock inner wells. */
    static boolean setStockTrim(String left,String right,double leftInner,double rightInner) {
        try {
            if(RV.wheelArch.count()<2 || !Double.isFinite(leftInner) || !Double.isFinite(rightInner)
                || leftInner<=0 || rightInner<=0 || leftInner>10000 || rightInner>10000)
                throw new IllegalArgumentException("stock inner band");
            float[][] roofs=new float[2][128];float[] limits=new float[64];int[] counts=new int[2];
            String[] sources={left,right};double[] inner={leftInner,rightInner};
            for(int side=0;side<2;side++) {
                if(sources[side]==null)throw new IllegalArgumentException("stock missing side");
                String[] spans=sources[side].split(";",-1);
                if(spans.length<1 || spans.length>32)throw new IllegalArgumentException("stock segment count");
                float previous=-Float.MAX_VALUE;
                for(String span:spans) {
                    String[] values=span.split(",",-1);
                    if(values.length!=5)throw new IllegalArgumentException("stock segment fields");
                    double[] d=new double[5];float[] f=new float[5];
                    for(int i=0;i<5;i++) {
                        d[i]=Double.parseDouble(values[i].trim());
                        if(!Double.isFinite(d[i]) || Math.abs(d[i])>10000)throw new IllegalArgumentException("stock finite bounds");
                        f[i]=(float)d[i];
                    }
                    if(d[0]>=d[1] || f[0]<previous || f[4]<=(float)inner[side] || f[4]>RV.wheelArch.halfWidth()+.00001f)
                        throw new IllegalArgumentException("stock order/band");
                    // A sub-ULP source span has no extent in the native float
                    // mesh. Omit only that zero-width quantized interval.
                    if(f[0]==f[1])continue;
                    int at=counts[side]++;
                    System.arraycopy(f,0,roofs[side],at*4,4);
                    limits[at*2+side]=f[4];previous=f[1];
                }
                if(counts[side]==0)throw new IllegalArgumentException("stock empty quantized side");
            }
            stock=new StockTrim(counts[0],counts[1],(float)leftInner,(float)rightInner,roofs[0],roofs[1],limits);
            return true;
        }catch(IllegalArgumentException invalid){RV.clearFlatWheelArch();return false;}
    }

    static void upload(ShaderProgram program, int mode) {
        upload(program, mode, false);
    }

    static void upload(ShaderProgram program, int mode, boolean proceduralWheelUV) {
        // Loose-item rendering shares this program. Every consumer resets the
        // buffer layout, so a wheel draw cannot change the next item's UVs.
        program.setValue("MELensWheelUV", mode == 2 && proceduralWheelUV ? 1f : 0f);
        RV.WheelArch arch = RV.wheelArch;
        boolean enabled = mode != 0 && RV.nativeBodyWalls && arch.count() >= 2 && Cutaway.shaderError == null;
        program.setVector4("MELensWheelArch", enabled ? mode : 0f,
                arch.halfWidth(), arch.floorZ(), enabled ? arch.count() : 0f);
        boolean curved=enabled && arch.leftCount()>=2 && arch.rightCount()>=2;
        program.setVector4("MELensWheelCurve",curved?arch.leftCount():0,curved?arch.rightCount():0,0f,0f);
        StockTrim trim=stock;
        boolean stockBody=enabled && mode==4 && trim!=StockTrim.NONE;
        program.setVector4("MELensWheelStock",stockBody?trim.leftCount():0,stockBody?trim.rightCount():0,
            stockBody?trim.leftInner():0,stockBody?trim.rightInner():0);
        if(stockBody) {
            int left=curveLocations.computeIfAbsent(program.getShaderID()+":stockLeft",
                key->GL20.glGetUniformLocation(program.getShaderID(),"MELensWheelStockLeft[0]"));
            int right=curveLocations.computeIfAbsent(program.getShaderID()+":stockRight",
                key->GL20.glGetUniformLocation(program.getShaderID(),"MELensWheelStockRight[0]"));
            int widths=curveLocations.computeIfAbsent(program.getShaderID()+":stockLimits",
                key->GL20.glGetUniformLocation(program.getShaderID(),"MELensWheelStockLimits[0]"));
            if(left<0 || right<0 || widths<0) {
                Cutaway.shaderError="Native stock-wheel trim uniforms missing from linked shader";
                program.setVector4("MELensWheelArch",0f,arch.halfWidth(),arch.floorZ(),0f);
                program.setVector4("MELensWheelStock",0f,0f,0f,0f);
                return;
            }
            GL20.glUniform4fv(left,trim.left());GL20.glUniform4fv(right,trim.right());GL20.glUniform2fv(widths,trim.limits());
            stockDraws.incrementAndGet();
        }
        float low = Float.POSITIVE_INFINITY, high = Float.NEGATIVE_INFINITY;
        float[] ring = RV.roomRing;
        for (int i=1;i<ring.length;i+=2) { low=Math.min(low,ring[i]); high=Math.max(high,ring[i]); }
        program.setVector4("MELensWheelBounds", Float.isFinite(low) ? low : 0f,
                Float.isFinite(high) ? high : 0f, 0f, 0f);
        if (enabled) {
            if(curved) {
                int left=curveLocations.computeIfAbsent(program.getShaderID()+":left",
                    key->GL20.glGetUniformLocation(program.getShaderID(),"MELensWheelLeft[0]"));
                int right=curveLocations.computeIfAbsent(program.getShaderID()+":right",
                    key->GL20.glGetUniformLocation(program.getShaderID(),"MELensWheelRight[0]"));
                if(left<0 || right<0) {
                    Cutaway.shaderError="Curved wheel arch uniforms missing from linked shader";
                    program.setVector4("MELensWheelArch",0f,arch.halfWidth(),arch.floorZ(),0f);
                    program.setVector4("MELensWheelCurve",0f,0f,0f,0f);
                    return;
                }
                GL20.glUniform3fv(left,arch.left());GL20.glUniform3fv(right,arch.right());
                if(mode==2)wheels.incrementAndGet();else if(mode==5)fittings.incrementAndGet();else interiors.incrementAndGet();
                return;
            }
            int location = locations.computeIfAbsent(program.getShaderID(),
                    id -> GL20.glGetUniformLocation(id, "MELensWheelContour[0]"));
            if (location < 0) {
                // An API opt-in alone must not hide the fallback covers when
                // the linked shader cannot execute the measured arch mask.
                Cutaway.shaderError = "Flat wheel arch contour uniform missing from linked shader";
                program.setVector4("MELensWheelArch", 0f, arch.halfWidth(), arch.floorZ(), 0f);
                return;
            }
            GL20.glUniform2fv(location, arch.upload());
            if (mode==2) wheels.incrementAndGet(); else if(mode==5) fittings.incrementAndGet(); else interiors.incrementAndGet();
        }
    }

    static String info() { return "wheels="+wheels.get()+";interiors="+interiors.get()+";stock="+stockDraws.get()+";fittings="+fittings.get(); }

    static boolean unboundedMesh(ModelMesh mesh) {
        return mesh != null && (mesh.minXyz.x > mesh.maxXyz.x || mesh.minXyz.y > mesh.maxXyz.y || mesh.minXyz.z > mesh.maxXyz.z
                || !Float.isFinite(mesh.minXyz.x) || !Float.isFinite(mesh.minXyz.y) || !Float.isFinite(mesh.minXyz.z)
                || !Float.isFinite(mesh.maxXyz.x) || !Float.isFinite(mesh.maxXyz.y) || !Float.isFinite(mesh.maxXyz.z));
    }

    /** Front wheels retain their untouched native draw. Check transformed rear bounds. */
    static boolean rearWheelCentre(Matrix4f toBody) {
        RV.WheelArch arch = RV.wheelArch;
        toBody.transformPosition(corner.set(0f,0f,0f));
        return arch.count() >= 2 && Float.isFinite(corner.x) && Float.isFinite(corner.y) && Float.isFinite(corner.z)
                && corner.y >= arch.upload()[0] && corner.y <= arch.upload()[(arch.count()-1)*2];
    }

    static boolean rearWheel(ModelMesh mesh, Matrix4f toBody) {
        if (mesh == null) return false;
        RV.WheelArch arch = RV.wheelArch;
        // The game's procedural Vehicles_Wheel renders with sentinel bounds
        // (min=Float.MAX_VALUE, max=-Float.MAX_VALUE). Its live transform still
        // supplies the wheel centre. Rejecting it by mesh bounds skipped every
        // vanilla tyre, while KI5's imported wheel meshes took the full path.
        if (unboundedMesh(mesh)) {
            return rearWheelCentre(toBody);
        }
        float low = Float.POSITIVE_INFINITY, high = Float.NEGATIVE_INFINITY;
        for (int i=0;i<8;i++) {
            corner.set((i&1)==0 ? mesh.minXyz.x : mesh.maxXyz.x,
                    (i&2)==0 ? mesh.minXyz.y : mesh.maxXyz.y,
                    (i&4)==0 ? mesh.minXyz.z : mesh.maxXyz.z);
            toBody.transformPosition(corner);
            low=Math.min(low,corner.y); high=Math.max(high,corner.y);
        }
        return arch.count() >= 2 && high >= arch.upload()[0]
                && low <= arch.upload()[(arch.count()-1)*2];
    }
}
