import React, { useState, useRef, useEffect } from 'react';
import axios from 'axios';

const QuestionsPanel = ({ questions, jobDescription, candidateName }) => {
  const [answers, setAnswers] = useState({});
  const [feedbacks, setFeedbacks] = useState({});
  const [techStackGrades, setTechStackGrades] = useState({});
  const [isRecording, setIsRecording] = useState(false);
  const [activeQuestion, setActiveQuestion] = useState(null);
  const [isEvaluating, setIsEvaluating] = useState(false);
  const [evaluation, setEvaluation] = useState(null);
  const [grades, setGrades] = useState({});
  const mediaRecorder = useRef(null);
  const audioChunks = useRef([]);
  const [yearsExperience, setYearsExperience] = useState("");

  const generalQuestions = questions.general_questions || [];
  const techQuestions = questions.tech_questions || [];
  const techStack = questions.tech_stack || [];
  const allQuestions = [...generalQuestions, ...techQuestions.map(tq => tq.question)];

  const startRecording = async (question) => {
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      mediaRecorder.current = new MediaRecorder(stream);
      audioChunks.current = [];
      setActiveQuestion(question);
      console.log(`Started recording for question: ${question}`);
      
      mediaRecorder.current.ondataavailable = (event) => {
        console.log('Audio data available');
        audioChunks.current.push(event.data);
      };

      mediaRecorder.current.onstop = async () => {
        console.log('Recording stopped, processing audio...');
        const audioBlob = new Blob(audioChunks.current, { type: 'audio/wav' });
        const formData = new FormData();
        formData.append('file', audioBlob, 'recording.wav');
        
        try {
          console.log('Sending audio for transcription...');
          console.log('Audio blob size:', audioBlob.size, 'bytes');
          
          const transcribeRes = await axios.post(
            'http://localhost:5001/transcribe-audio',
            formData,
            { 
              headers: { 'Content-Type': 'multipart/form-data' } 
            }
          );
          
          console.log('Transcription response:', transcribeRes);
          
          if (!transcribeRes.data || !transcribeRes.data.transcript) {
            console.error('Unexpected response format:', transcribeRes.data);
            throw new Error('Invalid response format from server');
          }
          
          const transcription = transcribeRes.data.transcript;
          console.log('Transcription received:', transcription);
          
          setAnswers(prev => ({ ...prev, [question]: transcription }));
          await handleSubmit(question, transcription);
          
        } catch (error) {
          console.error('Error in transcription process:', {
            error: error.message,
            response: error.response?.data,
            status: error.response?.status,
            statusText: error.response?.statusText
          });
          alert(`Failed to transcribe audio: ${error.message}`);
        }
      };
      
      mediaRecorder.current.start();
      setIsRecording(true);
      console.log('MediaRecorder started');
      
      // Set up a timer to log recording duration
      const startTime = Date.now();
      const timer = setInterval(() => {
        if (mediaRecorder.current && mediaRecorder.current.state === 'recording') {
          console.log(`Recording duration: ${((Date.now() - startTime) / 1000).toFixed(1)}s`);
        } else {
          clearInterval(timer);
        }
      }, 1000);
      
      // Store the interval ID to clear it later
      return () => clearInterval(timer);
      
    } catch (error) {
      console.error('Error accessing microphone:', {
        name: error.name,
        message: error.message,
        constraints: error.constraint
      });
      alert('Microphone access denied. Please allow microphone access to record your answers.');
    }
  };

  const stopRecording = () => {
    if (mediaRecorder.current && isRecording) {
      console.log('Stopping recording...');
      mediaRecorder.current.stop();
      mediaRecorder.current.stream.getTracks().forEach(track => {
        console.log(`Stopping track: ${track.kind}`);
        track.stop();
      });
      setIsRecording(false);
      setActiveQuestion(null);
    }
  };

  const handleSubmit = async (question, answerText) => {
    const answer = answerText || answers[question];
    if (!answer || answer.trim() === '') {
      alert('Please provide an answer before submitting.');
      return;
    }
    
    try {
      const techQuestion = techQuestions.find(tq => tq.question === question);
      
      const res = await axios.post("http://localhost:5001/evaluate-answer", { 
        question, 
        answer,
        technology: techQuestion ? techQuestion.technology : null
      });
      
      setFeedbacks(prev => ({ ...prev, [question]: res.data.feedback }));
      setGrades(prev => ({ ...prev, [question]: res.data.grade }));
      
      if (techQuestion) {
        setTechStackGrades(prev => ({ 
          ...prev, 
          [techQuestion.technology]: res.data.grade 
        }));
      }
    } catch (error) {
      console.error('Error evaluating answer:', error);
      alert('Failed to evaluate answer. Please try again.');
    }
  };

  const handleFinalEvaluation = async () => {
    if (Object.keys(answers).length === 0) {
      alert('Please answer at least one question before final evaluation.');
      return;
    }

    setIsEvaluating(true);
    try {
      // Collect feedbacks for each question if available
      const qaPairs = allQuestions.map((q) => ({
        question: q,
        answer: answers[q] || 'No answer provided',
        feedback: feedbacks[q] || ''
      }));

      const response = await axios.post('http://localhost:5001/final-evaluation', {
        job_description: jobDescription,
        qa_pairs: qaPairs,
        candidate_name: candidateName,
        years_experience: yearsExperience
      });

      if (response.data.success) {
        setEvaluation(response.data);
      } else {
        throw new Error(response.data.error || 'Failed to generate evaluation');
      }
    } catch (error) {
      console.error('Error during final evaluation:', error);
      alert(`Error: ${error.message}`);
    } finally {
      setIsEvaluating(false);
    }
  };

  // Clean up media recorder on unmount
  useEffect(() => {
    return () => {
      if (mediaRecorder.current && mediaRecorder.current.state !== 'inactive') {
        mediaRecorder.current.stop();
      }
    };
  }, []);

  return (
    <div>
      <h3>Interview Questions</h3>
      
      {generalQuestions.length > 0 && (
        <div style={{ marginBottom: '30px' }}>
          <h4 style={{ color: '#2c3e50', borderBottom: '2px solid #3498db', paddingBottom: '5px' }}>
            General Questions
          </h4>
          {generalQuestions.map((q, i) => (
            <div key={`general-${i}`} style={{ marginBottom: '20px', padding: '10px', border: '1px solid #ccc', borderRadius: '5px' }}>
              <p><b>{q}</b></p>
              <div style={{ margin: '10px 0' }}>
                {isRecording && activeQuestion === q ? (
                  <button 
                    onClick={stopRecording}
                    style={{
                      padding: '5px 10px',
                      backgroundColor: '#dc3545',
                      color: 'white',
                      border: 'none',
                      borderRadius: '4px',
                      marginRight: '10px',
                      cursor: 'pointer'
                    }}
                  >
                    Stop Recording
                  </button>
                ) : (
                  <button 
                    onClick={() => startRecording(q)}
                    style={{
                      padding: '5px 10px',
                      backgroundColor: '#28a745',
                      color: 'white',
                      border: 'none',
                      borderRadius: '4px',
                      marginRight: '10px',
                      cursor: 'pointer'
                    }}
                    disabled={isRecording}
                  >
                    Record Answer
                  </button>
                )}
                <button 
                  onClick={() => handleSubmit(q)}
                  style={{
                    padding: '5px 10px',
                    backgroundColor: '#007bff',
                    color: 'white',
                    border: 'none',
                    borderRadius: '4px',
                    cursor: 'pointer'
                  }}
                  disabled={!answers[q]}
                >
                  Submit Answer
                </button>
              </div>
              {answers[q] && (
                <div style={{ margin: '10px 0' }}>
                  <p><i>Your answer: {answers[q]}</i></p>
                </div>
              )}
              {feedbacks[q] && (
                <div style={{ marginTop: '10px', padding: '10px', backgroundColor: '#f8f9fa', borderRadius: '4px' }}>
                  <p>
                    <b>Grade:</b> {grades[q] !== undefined ? grades[q] : 'N/A'} / 10
                  </p>
                  <p>
                    <b>Feedback:</b> {feedbacks[q]}
                  </p>
                </div>
              )}
            </div>
          ))}
        </div>
      )}

      {techQuestions.length > 0 && (
        <div style={{ marginBottom: '30px' }}>
          <h4 style={{ color: '#2c3e50', borderBottom: '2px solid #e74c3c', paddingBottom: '5px' }}>
            Technical Questions
          </h4>
          {techQuestions.map((tq, i) => (
            <div key={`tech-${i}`} style={{ marginBottom: '20px', padding: '10px', border: '1px solid #e74c3c', borderRadius: '5px' }}>
              <div style={{ display: 'flex', alignItems: 'center', marginBottom: '10px' }}>
                <span style={{ 
                  backgroundColor: '#e74c3c', 
                  color: 'white', 
                  padding: '2px 8px', 
                  borderRadius: '12px', 
                  fontSize: '12px',
                  marginRight: '10px'
                }}>
                  {tq.technology}
                </span>
                {techStackGrades[tq.technology] && (
                  <span style={{ 
                    backgroundColor: '#27ae60', 
                    color: 'white', 
                    padding: '2px 8px', 
                    borderRadius: '12px', 
                    fontSize: '12px'
                  }}>
                    Grade: {techStackGrades[tq.technology]}/10
                  </span>
                )}
              </div>
              <p><b>{tq.question}</b></p>
              <div style={{ margin: '10px 0' }}>
                {isRecording && activeQuestion === tq.question ? (
                  <button 
                    onClick={stopRecording}
                    style={{
                      padding: '5px 10px',
                      backgroundColor: '#dc3545',
                      color: 'white',
                      border: 'none',
                      borderRadius: '4px',
                      marginRight: '10px',
                      cursor: 'pointer'
                    }}
                  >
                    Stop Recording
                  </button>
                ) : (
                  <button 
                    onClick={() => startRecording(tq.question)}
                    style={{
                      padding: '5px 10px',
                      backgroundColor: '#28a745',
                      color: 'white',
                      border: 'none',
                      borderRadius: '4px',
                      marginRight: '10px',
                      cursor: 'pointer'
                    }}
                    disabled={isRecording}
                  >
                    Record Answer
                  </button>
                )}
                <button 
                  onClick={() => handleSubmit(tq.question)}
                  style={{
                    padding: '5px 10px',
                    backgroundColor: '#007bff',
                    color: 'white',
                    border: 'none',
                    borderRadius: '4px',
                    cursor: 'pointer'
                  }}
                  disabled={!answers[tq.question]}
                >
                  Submit Answer
                </button>
              </div>
              {answers[tq.question] && (
                <div style={{ margin: '10px 0' }}>
                  <p><i>Your answer: {answers[tq.question]}</i></p>
                </div>
              )}
              {feedbacks[tq.question] && (
                <div style={{ marginTop: '10px', padding: '10px', backgroundColor: '#f8f9fa', borderRadius: '4px' }}>
                  <p>
                    <b>Grade:</b> {grades[tq.question] !== undefined ? grades[tq.question] : 'N/A'} / 10
                  </p>
                  <p>
                    <b>Feedback:</b> {feedbacks[tq.question]}
                  </p>
                </div>
              )}
            </div>
          ))}
        </div>
      )}

      {Object.keys(techStackGrades).length > 0 && (
        <div style={{ marginBottom: '30px', padding: '15px', backgroundColor: '#ecf0f1', borderRadius: '5px' }}>
          <h4>Tech Stack Performance</h4>
          <div style={{ display: 'flex', flexWrap: 'wrap', gap: '10px' }}>
            {Object.entries(techStackGrades).map(([tech, grade]) => (
              <div key={tech} style={{ 
                padding: '8px 12px', 
                backgroundColor: 'white', 
                borderRadius: '5px',
                border: '1px solid #bdc3c7'
              }}>
                <strong>{tech}:</strong> {grade}/10
              </div>
            ))}
          </div>
        </div>
      )}
      
      <div style={{ marginTop: '30px', padding: '20px', border: '1px solid #4CAF50', borderRadius: '5px' }}>
        <h3>Final Evaluation</h3>
        <button 
          onClick={handleFinalEvaluation}
          disabled={isEvaluating || Object.keys(answers).length === 0}
          style={{
            padding: '10px 20px',
            backgroundColor: isEvaluating || Object.keys(answers).length === 0 ? '#cccccc' : '#4CAF50',
            color: 'white',
            border: 'none',
            borderRadius: '4px',
            fontWeight: 'bold',
            cursor: isEvaluating || Object.keys(answers).length === 0 ? 'not-allowed' : 'pointer',
            marginBottom: '20px'
          }}
        >
          {isEvaluating ? 'Generating Evaluation...' : 'Generate Final Evaluation'}
        </button>

        {evaluation && (
          <div style={{ marginTop: '20px', padding: '15px', backgroundColor: '#f8f9fa', borderRadius: '5px' }}>
            <h4>Evaluation Results</h4>
            <p><strong>Overall Score:</strong> {evaluation.overall_score}/100</p>
            
            <div style={{ margin: '15px 0' }}>
              <h5>Strengths:</h5>
              <p style={{ whiteSpace: 'pre-line' }}>{evaluation.strengths}</p>
            </div>
            
            <div style={{ margin: '15px 0' }}>
              <h5>Areas for Improvement:</h5>
              <p style={{ whiteSpace: 'pre-line' }}>{evaluation.areas_for_improvement}</p>
            </div>
            
            <div style={{ margin: '15px 0' }}>
              <h5>Technical Assessment:</h5>
              <p style={{ whiteSpace: 'pre-line' }}>{evaluation.technical_assessment}</p>
            </div>
            
            <div style={{ margin: '15px 0' }}>
              <h5>Recommendations:</h5>
              <p style={{ whiteSpace: 'pre-line' }}>{evaluation.recommendations}</p>
            </div>
          </div>
        )}
      </div>
    </div>
  );
};

QuestionsPanel.defaultProps = {
  jobDescription: '',
  candidateName: ''
};

export default QuestionsPanel;