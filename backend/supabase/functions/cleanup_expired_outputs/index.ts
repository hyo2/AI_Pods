// Supabase Edge Function: cleanup_expired_outputs

import { serve } from "https://deno.land/std@0.168.0/http/server.ts";
import { createClient } from "https://esm.sh/@supabase/supabase-js@2";

const BUCKET = "project_resources";

serve(async () => {
  const supabaseUrl = Deno.env.get("SUPABASE_URL")!;
  const serviceRoleKey = Deno.env.get("SUPABASE_SERVICE_ROLE_KEY")!;
  const supabase = createClient(supabaseUrl, serviceRoleKey);

  const now = new Date();
  const nowISO = now.toISOString();

  let stats = {
    deletedOutputs: 0,
    deletedImages: 0,
    deletedInputs: 0,
    deletedFailedOutputs: 0,
    errors: [] as string[],
  };

  console.log(`[Cleanup Started] ${nowISO}`);

  // 1. status가 failed인 output_contents 삭제 (7일 경과)
  try {
    const sevenDaysAgo = new Date(now.getTime() - 7 * 24 * 60 * 60 * 1000).toISOString();

    const { data: failedOutputs, error: failedErr } = await supabase
      .from("output_contents")
      .select("id, audio_path, script_path, created_at")
      .eq("status", "failed")
      .lt("created_at", sevenDaysAgo);

    if (failedErr) {
      console.error("Failed outputs select error:", failedErr);
      stats.errors.push(`Failed outputs query: ${failedErr.message}`);
    } else if (failedOutputs && failedOutputs.length > 0) {
      console.log(`Found ${failedOutputs.length} failed outputs (>7 days old)`);

      for (const row of failedOutputs) {
        try {
          // 혹시 일부 파일이라도 생성되었다면 삭제
          if (row.audio_path) {
            await supabase.storage.from(BUCKET).remove([row.audio_path]);
          }
          if (row.script_path) {
            await supabase.storage.from(BUCKET).remove([row.script_path]);
          }

          // output_images도 함께 삭제
          const { data: imgs } = await supabase
            .from("output_images")
            .select("img_path")
            .eq("output_id", row.id);

          if (imgs) {
            for (const img of imgs) {
              if (img.img_path) {
                await supabase.storage.from(BUCKET).remove([img.img_path]);
              }
            }
            await supabase.from("output_images").delete().eq("output_id", row.id);
          }

          // DB row 삭제
          const { error: deleteErr } = await supabase
            .from("output_contents")
            .delete()
            .eq("id", row.id);

          if (deleteErr) {
            console.error(`Failed to delete output ${row.id}:`, deleteErr);
            stats.errors.push(`Output ${row.id}: ${deleteErr.message}`);
          } else {
            console.log(`Deleted failed output: ${row.id}`);
            stats.deletedFailedOutputs++;
          }
        } catch (err) {
          console.error(`Error processing failed output ${row.id}:`, err);
          stats.errors.push(`Output ${row.id}: ${err.message}`);
        }
      }
    }
  } catch (err) {
    console.error("Failed outputs cleanup error:", err);
    stats.errors.push(`Failed outputs: ${err.message}`);
  }

  // 2. status가 completed인 output_contents 삭제 (expires_at 기준)
  try {
    const { data: expiredOutputs, error: outputsErr } = await supabase
      .from("output_contents")
      .select("id, audio_path, script_path, expires_at")
      .eq("status", "completed")  // completed만 대상
      .lt("expires_at", nowISO);

    if (outputsErr) {
      console.error("Completed outputs select error:", outputsErr);
      stats.errors.push(`Completed outputs query: ${outputsErr.message}`);
    } else if (expiredOutputs && expiredOutputs.length > 0) {
      console.log(`Found ${expiredOutputs.length} expired completed outputs`);

      for (const row of expiredOutputs) {
        try {
          // Storage 파일 삭제
          if (row.audio_path) {
            const { error } = await supabase.storage
              .from(BUCKET)
              .remove([row.audio_path]);
            if (error) console.error(`Audio delete error (${row.id}):`, error);
            else console.log(`Deleted audio: ${row.audio_path}`);
          }

          if (row.script_path) {
            const { error } = await supabase.storage
              .from(BUCKET)
              .remove([row.script_path]);
            if (error) console.error(`Script delete error (${row.id}):`, error);
            else console.log(`Deleted script: ${row.script_path}`);
          }

          // output_images 함께 삭제
          const { data: images } = await supabase
            .from("output_images")
            .select("img_path")
            .eq("output_id", row.id);

          if (images) {
            for (const img of images) {
              if (img.img_path) {
                await supabase.storage.from(BUCKET).remove([img.img_path]);
              }
            }
            await supabase.from("output_images").delete().eq("output_id", row.id);
          }

          // DB row 삭제
          const { error: deleteErr } = await supabase
            .from("output_contents")
            .delete()
            .eq("id", row.id);

          if (deleteErr) {
            console.error(`Row delete error (${row.id}):`, deleteErr);
            stats.errors.push(`Output ${row.id}: ${deleteErr.message}`);
          } else {
            console.log(`Deleted completed output: ${row.id}`);
            stats.deletedOutputs++;
          }
        } catch (err) {
          console.error(`Error processing output ${row.id}:`, err);
          stats.errors.push(`Output ${row.id}: ${err.message}`);
        }
      }
    }
  } catch (err) {
    console.error("Completed outputs cleanup error:", err);
    stats.errors.push(`Completed outputs: ${err.message}`);
  }

  // 3. output_images 삭제 (독립적인 expires_at 있는 경우)
  try {
    const { data: expiredImages, error: imagesErr } = await supabase
      .from("output_images")
      .select("id, img_path, expires_at")
      .lt("expires_at", nowISO);

    if (imagesErr) {
      console.error("output_images select error:", imagesErr);
      stats.errors.push(`Images query: ${imagesErr.message}`);
    } else if (expiredImages && expiredImages.length > 0) {
      console.log(`Found ${expiredImages.length} expired output_images rows`);

      for (const row of expiredImages) {
        try {
          if (row.img_path) {
            const { error } = await supabase.storage
              .from(BUCKET)
              .remove([row.img_path]);
            if (error) console.error(`Image delete error (${row.id}):`, error);
            else console.log(`Deleted image: ${row.img_path}`);
          }

          const { error: deleteErr } = await supabase
            .from("output_images")
            .delete()
            .eq("id", row.id);

          if (deleteErr) {
            console.error(`Image row delete error (${row.id}):`, deleteErr);
            stats.errors.push(`Image ${row.id}: ${deleteErr.message}`);
          } else {
            stats.deletedImages++;
          }
        } catch (err) {
          console.error(`Error processing image ${row.id}:`, err);
          stats.errors.push(`Image ${row.id}: ${err.message}`);
        }
      }
    }
  } catch (err) {
    console.error("Images cleanup error:", err);
    stats.errors.push(`Images: ${err.message}`);
  }

  // 4. input_contents 삭제 (180일 미사용)
  try {
    const days180Ago = new Date(now.getTime() - 180 * 24 * 60 * 60 * 1000).toISOString();

    const { data: expiredInputs, error: inputsErr } = await supabase
      .from("input_contents")
      .select("id, storage_path, last_used_at")
      .lt("last_used_at", days180Ago);

    if (inputsErr) {
      console.error("input_contents select error:", inputsErr);
      stats.errors.push(`Inputs query: ${inputsErr.message}`);
    } else if (expiredInputs && expiredInputs.length > 0) {
      console.log(`Found ${expiredInputs.length} expired input_contents rows`);

      for (const row of expiredInputs) {
        try {
          if (row.storage_path) {
            const { error } = await supabase.storage
              .from(BUCKET)
              .remove([row.storage_path]);
            if (error) console.error(`Input file delete error (${row.id}):`, error);
            else console.log(`Deleted input file: ${row.storage_path}`);
          }

          const { error: delErr } = await supabase
            .from("input_contents")
            .delete()
            .eq("id", row.id);

          if (delErr) {
            console.error(`input_contents row delete error (${row.id}):`, delErr);
            stats.errors.push(`Input ${row.id}: ${delErr.message}`);
          } else {
            stats.deletedInputs++;
          }
        } catch (err) {
          console.error(`Error processing input ${row.id}:`, err);
          stats.errors.push(`Input ${row.id}: ${err.message}`);
        }
      }
    }
  } catch (err) {
    console.error("Inputs cleanup error:", err);
    stats.errors.push(`Inputs: ${err.message}`);
  }

  // 결과 요약
  console.log(`[Cleanup Completed]`);
  console.log(`- Deleted failed outputs: ${stats.deletedFailedOutputs}`);
  console.log(`- Deleted completed outputs: ${stats.deletedOutputs}`);
  console.log(`- Deleted images: ${stats.deletedImages}`);
  console.log(`- Deleted inputs: ${stats.deletedInputs}`);
  console.log(`- Errors: ${stats.errors.length}`);

  if (stats.errors.length > 0) {
    console.error("Errors encountered:", stats.errors);
  }

  return new Response(
    JSON.stringify({
      success: true,
      timestamp: nowISO,
      stats,
    }),
    {
      headers: { "Content-Type": "application/json" },
    }
  );
});