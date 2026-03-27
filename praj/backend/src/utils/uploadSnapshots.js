const supabase = require("../config/supabase");

const uploadSnapshot = async (fileBuffer, originalName, mimeType) => {
    // const fileName = ⁠ `snapshots/${Date.now()}_${originalName}`⁠;
    const fileName = `snapshots/${Date.now()}_${originalName}`

    // Upload to Supabase bucket
    const { error } = await supabase.storage
        .from(process.env.SUPABASE_BUCKET)
        .upload(fileName, fileBuffer, {
            contentType: mimeType,
        });

    if (error) throw error;

    // Get public URL
    const { data } = supabase.storage
        .from(process.env.SUPABASE_BUCKET)
        .getPublicUrl(fileName);

    return data.publicUrl;
};

module.exports = uploadSnapshot;