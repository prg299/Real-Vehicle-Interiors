// Named source roof models also contain necessary upper side walls. Classify
// whole geometric faces: their custom smooth normals cross the measured cutoff.
uniform vec4 MELensRoofCut0;
uniform vec4 MELensRoofCut1;
uniform vec4 MELensRoofCut2;
uniform vec4 MELensRoofCut3;
uniform vec3 MELensRoofMin0;
uniform vec3 MELensRoofMin1;
uniform vec3 MELensRoofMin2;
uniform vec3 MELensRoofMin3;
uniform vec3 MELensRoofMax0;
uniform vec3 MELensRoofMax1;
uniform vec3 MELensRoofMax2;
uniform vec3 MELensRoofMax3;
uniform vec4 MELensRoofUV0;
uniform vec4 MELensRoofUV1;
uniform vec4 MELensRoofUV2;
uniform vec4 MELensRoofUV3;

bool meLensSourceRegion(vec3 p, vec2 uv, vec4 rule, vec3 lo, vec3 hi, vec4 boxUV)
{
    return rule.w > 0.5
        && (rule.y < 0.5 || (p.x >= lo.x && p.y >= lo.y && p.z >= lo.z
                            && p.x <= hi.x && p.y <= hi.y && p.z <= hi.z))
        && (rule.z < 0.5 || (uv.x >= boxUV.x && uv.y >= boxUV.y
                            && uv.x <= boxUV.z && uv.y <= boxUV.w));
}

bool meLensRoofRegion(vec3 p, vec2 uv, float up, vec4 rule, vec3 lo, vec3 hi, vec4 boxUV)
{
    return rule.w < 1.5 && (rule.x < 0.0 || up > rule.x)
        // Only geometric roof cuts yield to the measured door bay. Negative
        // thresholds are seat/fitting cuts and must keep removing intrusions.
        && !(rule.x >= 0.0 && meLensFrontKept(p))
        && meLensSourceRegion(p,uv,rule,lo,hi,boxUV);
}

float meLensSideEdgeRegion(vec3 p, vec2 uv, vec2 camera, vec4 rule, vec3 lo, vec3 hi, vec4 boxUV)
{
    if(rule.w < 1.5 || !meLensSourceRegion(p,uv,rule,lo,hi,boxUV)) return -1.0;
    return step(0.001,camera.x*(rule.w>2.5?1.0:-1.0));
}

float meLensSideEdgeNear(vec3 p, vec2 uv, vec2 camera, vec3 normal)
{
    // Only the tangential end face inherits its parent side wall. Broad door
    // skins and glazing keep their geometric classification and native masks.
    if(abs(normal.y)/max(length(normal),0.000001)<0.98)return -1.0;
    float result=meLensSideEdgeRegion(p,uv,camera,MELensRoofCut0,MELensRoofMin0,MELensRoofMax0,MELensRoofUV0);
    if(result>=0.0)return result;
    result=meLensSideEdgeRegion(p,uv,camera,MELensRoofCut1,MELensRoofMin1,MELensRoofMax1,MELensRoofUV1);
    if(result>=0.0)return result;
    result=meLensSideEdgeRegion(p,uv,camera,MELensRoofCut2,MELensRoofMin2,MELensRoofMax2,MELensRoofUV2);
    if(result>=0.0)return result;
    return meLensSideEdgeRegion(p,uv,camera,MELensRoofCut3,MELensRoofMin3,MELensRoofMax3,MELensRoofUV3);
}

bool meLensRoofRemoved(vec3 p, vec2 uv, vec3 bodyUp)
{
    if (MELensRoofCut0.w + MELensRoofCut1.w + MELensRoofCut2.w + MELensRoofCut3.w < 0.5)
        return false;
    vec3 geometric = cross(dFdx(p), dFdy(p));
    float up = abs(dot(geometric / max(length(geometric), 0.000001), normalize(bodyUp)));
    return meLensRoofRegion(p, uv, up, MELensRoofCut0, MELensRoofMin0, MELensRoofMax0, MELensRoofUV0)
        || meLensRoofRegion(p, uv, up, MELensRoofCut1, MELensRoofMin1, MELensRoofMax1, MELensRoofUV1)
        || meLensRoofRegion(p, uv, up, MELensRoofCut2, MELensRoofMin2, MELensRoofMax2, MELensRoofUV2)
        || meLensRoofRegion(p, uv, up, MELensRoofCut3, MELensRoofMin3, MELensRoofMax3, MELensRoofUV3);
}

