@app.post("/api/v1/analyze", response_model=AnalyzeResponse)
async def analyze(request: AnalyzeRequest):
    """Analyze tone (complete sentences recommended for best results)"""

    if not pipeline:
        raise HTTPException(503, "Pipeline not ready")

    try:
        result = pipeline.process(request.text)

        if result.get("error"):
            raise HTTPException(400, result.get("reason"))

        freq_type = result["freq_type"]
        confidence = result["confidence"]["final"]
        repaired_text = result["output"].get("repaired_text")
        repair_note = None

        if freq_type == "Unknown" or confidence < 0.3:
            repaired_text, repair_note = generate_contextual_response(
                request.text, freq_type, confidence
            )

        log_id = None
        if data_logger:
            try:
                log = data_logger.log_analysis(  # ← 改成 log_analysis
                    input_text=request.text,
                    output_result=result,
                    metadata={
                        "confidence": confidence,
                        "freq_type": freq_type,
                        "text_length": len(request.text),
                    },
                )
                log_id = log.get("timestamp")
            except Exception as log_error:
                logger.warning(f"⚠️ Logging failed: {log_error}")

        return AnalyzeResponse(
            original=result["original"],
            freq_type=freq_type,
            confidence=confidence,
            scenario=result["output"]["scenario"],
            repaired_text=repaired_text,
            repair_note=repair_note,
            log_id=log_id,
        )
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Analysis error: {str(e)}")
        import traceback
        traceback.print_exc()
        raise HTTPException(500, f"Analysis failed: {str(e)}")
