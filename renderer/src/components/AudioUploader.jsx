import React, { useState } from 'react';
import axios from 'axios';

const AudioUploader = () => {
  const [transcript, setTranscript] = useState("");

  const handleUpload = async (e) => {
    const file = e.target.files[0];
    const form = new FormData();
    form.append("file", file);
    const res = await axios.post("http://localhost:5001/transcribe-audio", form);
    setTranscript(res.data.transcript);
  };

  return (
    <div>
      <h3>Upload Audio Response</h3>
      <input type="file" accept="audio/*" onChange={handleUpload} />
      {transcript && <p><b>Transcript:</b> {transcript}</p>}
    </div>
  );
};

export default AudioUploader;