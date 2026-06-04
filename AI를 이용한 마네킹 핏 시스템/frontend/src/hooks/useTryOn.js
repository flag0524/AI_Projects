import { useState, useRef, useCallback } from "react";
import axios from "axios";

const POLL_INTERVAL = 2000;
const MAX_POLL = 150; // 5분

export function useTryOn() {
  const [status, setStatus] = useState("idle");
  // idle | uploading | processing | done | error
  const [progress, setProgress] = useState({ step: "", pct: 0 });
  const [results, setResults] = useState([]);
  const [fitReport, setFitReport] = useState(null);
  const [error, setError] = useState(null);
  const pollRef = useRef(null);

  const stopPolling = () => {
    if (pollRef.current) clearInterval(pollRef.current);
  };

  const _poll = useCallback((jobId) => {
    let count = 0;
    stopPolling();
    pollRef.current = setInterval(async () => {
      count++;
      if (count > MAX_POLL) {
        stopPolling();
        setStatus("error");
        setError("생성 시간이 너무 오래 걸립니다. 잠시 후 다시 시도해주세요.");
        return;
      }
      try {
        const { data: job } = await axios.get(`/api/v1/tryon/${jobId}`);

        if (job.progress != null) {
          setProgress({ step: job.step || "", pct: job.progress });
        }

        if (job.status === "succeeded") {
          stopPolling();
          setResults(job.results);
          setFitReport(job.results[0]?.fit_report ?? null);
          setStatus("done");
        } else if (job.status === "failed") {
          stopPolling();
          setStatus("error");
          setError(job.error || "생성 중 오류가 발생했습니다.");
        }
      } catch {
        // 네트워크 오류는 무시하고 계속 폴링
      }
    }, POLL_INTERVAL);
  }, []);

  // 단일 카테고리
  const submit = useCallback(async ({ mannequinFile, garmentFile, form }) => {
    setStatus("uploading");
    setError(null);
    setResults([]);
    setFitReport(null);
    setProgress({ step: "업로드 중", pct: 0 });

    try {
      const fd = new FormData();
      fd.append("mannequin_image", mannequinFile);
      fd.append("garment_image", garmentFile);
      fd.append("category", form.category);
      fd.append("fit_mode", form.fitMode);
      fd.append("num_candidates", form.numCandidates);
      fd.append("remove_background", form.removeBackground);
      if (form.seed) fd.append("seed", form.seed);

      const sizeObj = _buildSizeObj(form.size);
      if (sizeObj) fd.append("garment_size", JSON.stringify(sizeObj));

      const { data } = await axios.post("/api/v1/tryon", fd);
      setStatus("processing");
      setProgress({ step: "대기 중", pct: 5 });
      _poll(data.job_id);
    } catch (e) {
      setStatus("error");
      setError(e.response?.data?.detail || "요청 중 오류가 발생했습니다.");
    }
  }, [_poll]);

  // 레이어링 (상의+하의)
  const submitLayered = useCallback(async ({ mannequinFile, topFile, bottomFile, form }) => {
    setStatus("uploading");
    setError(null);
    setResults([]);
    setFitReport(null);
    setProgress({ step: "업로드 중", pct: 0 });

    try {
      const fd = new FormData();
      fd.append("mannequin_image", mannequinFile);
      fd.append("top_image", topFile);
      fd.append("bottom_image", bottomFile);
      fd.append("fit_mode", form.fitMode);
      fd.append("remove_background", form.removeBackground);
      if (form.seed) fd.append("seed", form.seed);

      const topSize = _buildSizeObj(form.topSize);
      const bottomSize = _buildSizeObj(form.bottomSize);
      if (topSize) fd.append("top_size", JSON.stringify(topSize));
      if (bottomSize) fd.append("bottom_size", JSON.stringify(bottomSize));

      const { data } = await axios.post("/api/v1/tryon/layered", fd);
      setStatus("processing");
      setProgress({ step: "레이어링 준비 중", pct: 5 });
      _poll(data.job_id);
    } catch (e) {
      setStatus("error");
      setError(e.response?.data?.detail || "요청 중 오류가 발생했습니다.");
    }
  }, [_poll]);

  // 재생성 — 같은 파라미터로 seed만 변경
  const regenerate = useCallback(async (jobId, newSeed) => {
    // job_id를 이용한 재생성은 서버에서 지원 예정
    // 현재는 클라이언트에서 seed+1로 재요청 유도
    setStatus("processing");
    setProgress({ step: "재생성 중", pct: 10 });
    _poll(jobId);
  }, [_poll]);

  const reset = useCallback(() => {
    stopPolling();
    setStatus("idle");
    setResults([]);
    setFitReport(null);
    setError(null);
    setProgress({ step: "", pct: 0 });
  }, []);

  return { status, progress, results, fitReport, error, submit, submitLayered, regenerate, reset };
}

function _buildSizeObj(sizeForm) {
  if (!sizeForm) return null;
  const keys = ["total_length", "chest", "shoulder", "sleeve", "waist", "hip"];
  const obj = { unit: "cm" };
  let has = false;
  for (const k of keys) {
    const v = parseFloat(sizeForm[k]);
    if (!isNaN(v) && v > 0) { obj[k] = v; has = true; }
  }
  return has ? obj : null;
}
