import React, { useState } from 'react';
import axios from 'axios';

const JDInput = ({ setQuestions, setJobDescription, onCandidateNameChange }) => {
  const [jd, setJd] = useState("");
  const [candidateName, setCandidateName] = useState("");
  const [techStacks, setTechStacks] = useState([]);
  const [numQuestions, setNumQuestions] = useState(5);
  const [yearsExperience, setYearsExperience] = useState("");

  const handleGenerate = async () => {
    if (!jd.trim()) {
      alert('Please enter a job description');
      return;
    }
    if (!candidateName.trim()) {
      alert('Please enter the candidate\'s name');
      return;
    }
    
    try {
      setJobDescription(jd);
      onCandidateNameChange(candidateName);
      
      const res = await axios.post("http://localhost:5001/generate-questions", { 
        job_description: jd,
        num_questions: numQuestions,
        years_experience: yearsExperience
      });
      
      const questionsData = res.data.questions;
      setQuestions(questionsData);
      setTechStacks(questionsData.tech_stack || []);
    } catch (error) {
      console.error('Error generating questions:', error);
      alert('Failed to generate questions. Please try again.');
    }
  };

  return (
    <div>
      <div style={{ marginBottom: '15px' }}>
        <h3>Candidate Name</h3>
        <input 
          type="text" 
          value={candidateName} 
          onChange={e => setCandidateName(e.target.value)} 
          placeholder="Enter candidate's name"
          style={{ padding: '8px', width: '300px' }}
        />
      </div>
      <div>
        <h3>Enter Job Description</h3>
        <textarea 
          value={jd} 
          onChange={e => setJd(e.target.value)} 
          placeholder="Paste the job description here..."
          style={{
            padding: '12px',
            width: '100%',
            minHeight: '150px',
            maxHeight: '500px',
            resize: 'vertical',
            boxSizing: 'border-box',
            borderRadius: '4px',
            border: '1px solid #ddd',
            fontFamily: 'inherit',
            fontSize: '14px',
            lineHeight: '1.5',
            overflowY: 'auto'
          }}
        />
      </div>
      <div>
        <h4>Number of Questions</h4>
        <input 
          type="number"
          value={numQuestions}
          onChange={(e) => setNumQuestions(parseInt(e.target.value) || 5)}
          placeholder="Enter number of questions"
          min="1"
          max="20"
        />
      </div>
      <div>
        <h4>Years of Experience</h4>
        <input
          type="number"
          value={yearsExperience}
          onChange={e => setYearsExperience(e.target.value)}
          placeholder="Enter years of experience"
          min="0"
          max="50"
        />
      </div>
      <br />
      <button 
        onClick={handleGenerate}
        disabled={!jd.trim() || !candidateName.trim()}
        style={{
          padding: '8px 16px',
          backgroundColor: (!jd.trim() || !candidateName.trim()) ? '#cccccc' : '#007bff',
          color: 'white',
          border: 'none',
          borderRadius: '4px',
          cursor: (!jd.trim() || !candidateName.trim()) ? 'not-allowed' : 'pointer'
        }}
      >
        Generate Questions
      </button>
      
      {techStacks.length > 0 && (
        <div style={{ marginTop: '20px', padding: '15px', backgroundColor: '#f8f9fa', borderRadius: '5px' }}>
          <h3>Identified Tech Stack</h3>
          <div style={{ display: 'flex', flexWrap: 'wrap', gap: '8px' }}>
            {techStacks.map((tech, index) => (
              <span 
                key={index}
                style={{
                  padding: '4px 8px',
                  backgroundColor: '#e9ecef',
                  borderRadius: '4px',
                  fontSize: '14px'
                }}
              >
                {tech}
              </span>
            ))}
          </div>
        </div>
      )}
    </div>
  );
};

JDInput.defaultProps = {
  onCandidateNameChange: () => {}
};

export default JDInput;