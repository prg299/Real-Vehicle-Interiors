// Shared reciprocal arch visibility. Body coordinates: x across, y front, z down.
varying vec3 meLensBodyViewRay;
uniform vec4 MELensWheelArch; // mode: 0 off,1 interior,2 wheel,3 native finish,4 stock,5 exterior arch fitting; half-width,floor z,count
uniform vec4 MELensWheelBounds; // floor front-axis min/max
uniform vec2 MELensWheelContour[16]; // front-axis position, native arch height
uniform vec4 MELensWheelCurve; // left/right point counts; zero retains the original planar path
uniform vec3 MELensWheelLeft[16];  // front axis, down height, signed across axis
uniform vec3 MELensWheelRight[16];
uniform vec4 MELensWheelStock; // left/right segment counts, left/right inner limits
uniform vec4 MELensWheelStockLeft[32]; // front min/max, roof down at each end
uniform vec4 MELensWheelStockRight[32];
uniform vec2 MELensWheelStockLimits[32]; // separately qualified outer limits per interval

bool meLensStockWellRemoved(vec3 p)
{
    // The stock trim envelope touches the side door's lower edge return.
    if (meLensFrontKept(p)) return false;
    if(p.z>=MELensWheelArch.z)return false;
    bool positive=p.x>0.0;
    float width=abs(p.x);
    float inner=positive?MELensWheelStock.w:MELensWheelStock.z;
    if(width<inner)return false;
    int count=int((positive?MELensWheelStock.y:MELensWheelStock.x)+0.5);
    for(int i=0;i<32;i++)
    {
        if(i>=count)break;
        vec4 span=positive?MELensWheelStockRight[i]:MELensWheelStockLeft[i];
        float outer=positive?MELensWheelStockLimits[i].y:MELensWheelStockLimits[i].x;
        if(width>outer || p.y<span.x || p.y>span.y)continue;
        float roof=mix(span.z,span.w,(p.y-span.x)/(span.y-span.x));
        if(p.z>=roof)return true;
    }
    return false;
}

bool meLensCurvedCrossing(vec3 p, vec3 ray, bool positive, bool floorEntry)
{
    int count=int((positive?MELensWheelCurve.y:MELensWheelCurve.x)+0.5);
    for(int i=0;i<15;i++)
    {
        if(i+1>=count)break;
        vec3 a=positive?MELensWheelRight[i]:MELensWheelLeft[i];
        vec3 b=positive?MELensWheelRight[i+1]:MELensWheelLeft[i+1];
        float slope=(b.z-a.z)/(b.x-a.x);
        float divisor=ray.x-slope*ray.y;
        if(abs(divisor)<0.00001)continue;
        float t=(a.z+slope*(p.y-a.x)-p.x)/divisor;
        if(t< -0.0001)continue;
        vec3 hit=p+ray*max(t,0.0);
        if(hit.y<a.x || hit.y>b.x)continue;
        if(floorEntry && hit.z<MELensWheelArch.z)return true;
        float archZ=mix(a.y,b.y,(hit.y-a.x)/(b.x-a.x));
        if(!floorEntry && hit.z>archZ+0.0001)return true;
    }
    return false;
}

// The tyre has width: its inner sidewall can already stand inside the hull.
// A forward ray from that fragment never crosses the far hull, and projecting
// it down to the floor can land outside the room. Classify that volume at the
// fragment's own station before attempting either reciprocal projection.
bool meLensInsideFarCurvedWall(vec3 p)
{
    bool positive=p.x>0.0;
    int count=int((positive?MELensWheelCurve.y:MELensWheelCurve.x)+0.5);
    for(int i=0;i<15;i++)
    {
        if(i+1>=count)break;
        vec3 a=positive?MELensWheelRight[i]:MELensWheelLeft[i];
        vec3 b=positive?MELensWheelRight[i+1]:MELensWheelLeft[i+1];
        if(p.y<a.x || p.y>b.x)continue;
        float side=mix(a.z,b.z,(p.y-a.x)/(b.x-a.x));
        return positive?p.x<=side:p.x>=side;
    }
    return false;
}

bool meLensThroughArch(vec3 p, vec3 ray)
{
    if (abs(ray.x) < 0.00001) return false;
    if(MELensWheelCurve.x>1.5 && MELensWheelCurve.y>1.5)
        return meLensCurvedCrossing(p,ray,ray.x>0.0,false);
    float side = ray.x > 0.0 ? MELensWheelArch.y : -MELensWheelArch.y;
    float t = (side - p.x) / ray.x;
    if (t < -0.0001) return false;
    vec3 hit = p + ray * max(t, 0.0);
    int count = int(MELensWheelArch.w + 0.5);
    for (int i = 0; i < 15; i++)
    {
        if (i + 1 >= count) break;
        vec2 a = MELensWheelContour[i];
        vec2 b = MELensWheelContour[i + 1];
        if (hit.y >= a.x && hit.y <= b.x)
        {
            float fraction = (hit.y - a.x) / max(b.x - a.x, 0.00001);
            float archZ = mix(a.y, b.y, fraction);
            return hit.z > archZ + 0.0001;
        }
    }
    return false;
}

bool meLensWheelRemoved(vec3 p)
{
    if (MELensWheelArch.x < 0.5) return false;
    vec3 ray = normalize(meLensBodyViewRay);
    if ((MELensWheelArch.x > 1.5 && MELensWheelArch.x < 2.5) || MELensWheelArch.x > 4.5)
    {
        // The far tyre can project onto the inward arch wall rather than the
        // floor. Its outer tread then has a floor projection outside the room.
        // Clip where the ray enters the hull above the floor, matching that
        // wall's footprint instead of retaining tread in front of its finish.
        if (p.x * ray.x < 0.0 && abs(ray.x) > 0.00001)
        {
            if(MELensWheelCurve.x>1.5 && MELensWheelCurve.y>1.5)
            {
                if(p.z<MELensWheelArch.z && meLensInsideFarCurvedWall(p))return true;
                if(meLensCurvedCrossing(p,ray,p.x>0.0,true))return true;
            }
            else
            {
            float farSide = p.x > 0.0 ? MELensWheelArch.y : -MELensWheelArch.y;
            float enter = max((farSide - p.x) / ray.x, 0.0);
            if ((p + ray * enter).z < MELensWheelArch.z) return true;
            }
        }
        // Project onto the same floor used by the interior pass. Starting at an
        // outward tyre face would miss the arch crossing behind that fragment.
        if (p.z >= MELensWheelArch.z || abs(ray.z) < 0.00001) return false;
        vec3 floorPoint = p + ray * ((MELensWheelArch.z - p.z) / ray.z);
        bool interior = abs(floorPoint.x) < MELensWheelArch.y
            && floorPoint.y >= MELensWheelBounds.x && floorPoint.y <= MELensWheelBounds.y;
        return interior && !meLensThroughArch(floorPoint, ray);
    }
    return meLensThroughArch(p, ray);
}
