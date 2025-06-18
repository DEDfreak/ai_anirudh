import React, { useState } from 'react';
import JDInput from './components/JDInput';
import QuestionsPanel from './components/QuestionsPanel';
import AudioUploader from './components/AudioUploader';

const App = () => {
  const [questions, setQuestions] = useState([]);
  const [jobDescription, setJobDescription] = useState('');
  const [candidateName, setCandidateName] = useState('');

  return (
    <div id="app-root" style={{ padding: '20px', maxWidth: '1200px', margin: '0 auto' }}>
      <h1>AI Interview Assistant</h1>
      <JDInput 
        setQuestions={setQuestions} 
        setJobDescription={setJobDescription}
        onCandidateNameChange={setCandidateName}
      />
      {Object.keys(questions).length > 0 && (
        <QuestionsPanel 
          questions={questions} 
          jobDescription={jobDescription}
          candidateName={candidateName}
        />
      )}
      <AudioUploader />
    </div>
  );
};

export default App;