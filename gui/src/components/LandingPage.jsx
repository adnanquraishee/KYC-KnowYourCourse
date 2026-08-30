import React, { useState, useRef } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import {
  Upload,
  FileText,
  CheckCircle2,
  Sparkles,
  BookOpen,
  ArrowRight,
  ShieldCheck,
  Compass,
  GraduationCap,
  Loader2,
  AlertCircle,
  FolderSync,
} from 'lucide-react';

export default function LandingPage({
  onLaunch,
  onUploadCatalogue,
  uploadLoading,
  uploadError,
  uploadedCatalogue,
}) {
  const [dragActive, setDragActive] = useState(false);
  const [selectedFile, setSelectedFile] = useState(null);
  const fileInputRef = useRef(null);

  const handleDrag = (e) => {
    e.preventDefault();
    e.stopPropagation();
    if (e.type === 'dragenter' || e.type === 'dragover') {
      setDragActive(true);
    } else if (e.type === 'dragleave') {
      setDragActive(false);
    }
  };

  const handleDrop = (e) => {
    e.preventDefault();
    e.stopPropagation();
    setDragActive(false);
    if (e.dataTransfer.files && e.dataTransfer.files[0]) {
      const file = e.dataTransfer.files[0];
      if (file.type === 'application/pdf' || file.name.endsWith('.pdf')) {
        setSelectedFile(file);
      } else {
        alert('Please upload a PDF file (.pdf)');
      }
    }
  };

  const handleChange = (e) => {
    e.preventDefault();
    if (e.target.files && e.target.files[0]) {
      const file = e.target.files[0];
      if (file.name.endsWith('.pdf') || file.type === 'application/pdf') {
        setSelectedFile(file);
      } else {
        alert('Please upload a PDF file (.pdf)');
      }
    }
  };

  const handleUploadSubmit = () => {
    if (selectedFile && onUploadCatalogue) {
      onUploadCatalogue(selectedFile);
    }
  };

  return (
    <div className="landing-container">
      {/* Header Banner */}
      <header className="landing-nav">
        <div className="landing-brand">
          <span className="brand-badge-icon">
            <GraduationCap size={18} />
          </span>
          <span className="brand-title">KYC</span>
          <span className="brand-sub">Know Your Courses</span>
        </div>
        <div className="landing-nav-badge">
          <span className="live-dot" />
          <span>Agentic RAG Engine</span>
        </div>
      </header>

      {/* Hero Section */}
      <main className="landing-main">
        <motion.div
          className="hero-header"
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.6 }}
        >
          <div className="hero-pill">
            <Sparkles size={14} className="pill-icon" />
            <span>AI Syllabus & Course Intelligence</span>
          </div>

          <h1 className="hero-title">
            Upload your Course Catalogue. <br />
            <span className="title-gradient">Master your curriculum.</span>
          </h1>

          <p className="hero-subtitle">
            An agentic retrieval assistant that reads your institution's course catalogue cover to cover.
            Ask about course credits, career electives, or prerequisite roadmaps with verified page citations.
          </p>
        </motion.div>

        {/* Upload & Onboarding Grid */}
        <div className="onboarding-grid">
          {/* Card 1: Upload Custom Catalogue */}
          <motion.div
            className="upload-card"
            initial={{ opacity: 0, x: -20 }}
            animate={{ opacity: 1, x: 0 }}
            transition={{ duration: 0.5, delay: 0.15 }}
          >
            <div className="card-header">
              <div className="card-icon-box upload-accent">
                <Upload size={20} />
              </div>
              <div>
                <h3 className="card-title">Upload Your Syllabus / Catalogue</h3>
                <p className="card-desc">PDF format, up to 50 MB</p>
              </div>
            </div>

            <div
              className={`dropzone ${dragActive ? 'active' : ''} ${selectedFile ? 'has-file' : ''}`}
              onDragEnter={handleDrag}
              onDragLeave={handleDrag}
              onDragOver={handleDrag}
              onDrop={handleDrop}
              onClick={() => !uploadLoading && fileInputRef.current?.click()}
            >
              <input
                ref={fileInputRef}
                type="file"
                accept=".pdf,application/pdf"
                className="hidden-file-input"
                onChange={handleChange}
                disabled={uploadLoading}
              />

              {!selectedFile && !uploadedCatalogue ? (
                <div className="dropzone-content">
                  <div className="dropzone-icon">
                    <FileText size={32} />
                  </div>
                  <p className="dropzone-prompt">
                    <strong>Drag & drop your PDF</strong> or <span className="browse-link">browse files</span>
                  </p>
                  <span className="dropzone-hint">Supports full course catalogues, syllabus briefs, curriculum guides</span>
                </div>
              ) : selectedFile && !uploadedCatalogue ? (
                <div className="file-preview-box">
                  <FileText size={28} className="file-icon" />
                  <div className="file-meta">
                    <span className="file-name">{selectedFile.name}</span>
                    <span className="file-size">{(selectedFile.size / (1024 * 1024)).toFixed(2)} MB</span>
                  </div>
                  <button
                    type="button"
                    className="change-file-btn"
                    onClick={(e) => {
                      e.stopPropagation();
                      setSelectedFile(null);
                    }}
                  >
                    Change
                  </button>
                </div>
              ) : (
                <div className="uploaded-success-box">
                  <CheckCircle2 size={32} className="success-icon" />
                  <div className="uploaded-meta">
                    <span className="uploaded-name">{uploadedCatalogue.filename}</span>
                    <span className="uploaded-stats">
                      {uploadedCatalogue.pages} pages • {uploadedCatalogue.chunks} vector chunks indexed
                    </span>
                  </div>
                </div>
              )}
            </div>

            {uploadError && (
              <div className="upload-error-pill">
                <AlertCircle size={14} />
                <span>{uploadError}</span>
              </div>
            )}

            <div className="card-actions">
              {selectedFile && !uploadedCatalogue ? (
                <button
                  type="button"
                  className="primary-action-btn"
                  onClick={handleUploadSubmit}
                  disabled={uploadLoading}
                >
                  {uploadLoading ? (
                    <>
                      <Loader2 size={16} className="spin" />
                      <span>Parsing & Indexing PDF...</span>
                    </>
                  ) : (
                    <>
                      <FolderSync size={16} />
                      <span>Index & Launch Assistant</span>
                    </>
                  )}
                </button>
              ) : uploadedCatalogue ? (
                <button
                  type="button"
                  className="primary-action-btn launch"
                  onClick={() => onLaunch(uploadedCatalogue)}
                >
                  <span>Open KYC Assistant</span>
                  <ArrowRight size={16} />
                </button>
              ) : (
                <button
                  type="button"
                  className="primary-action-btn secondary"
                  onClick={() => fileInputRef.current?.click()}
                >
                  <Upload size={15} />
                  <span>Select Catalogue PDF</span>
                </button>
              )}
            </div>
          </motion.div>

          {/* Card 2: Quick Start with Preloaded Catalogue */}
          <motion.div
            className="quickstart-card"
            initial={{ opacity: 0, x: 20 }}
            animate={{ opacity: 1, x: 0 }}
            transition={{ duration: 0.5, delay: 0.2 }}
          >
            <div className="card-header">
              <div className="card-icon-box sample-accent">
                <BookOpen size={20} />
              </div>
              <div>
                <h3 className="card-title">Or Try the Preloaded Catalogue</h3>
                <p className="card-desc">Zero setup required — jump right in</p>
              </div>
            </div>

            <div className="sample-card-body">
              <div className="sample-badge">
                <span className="sample-pill">Featured Dataset</span>
              </div>
              <h4 className="sample-title">JAGSoM PGDM 2025–27 Catalogue</h4>
              <p className="sample-desc">
                Includes 98 pages of course briefs across Finance, Marketing, Business Analytics, HRM, and general management with electives and pre-requisite mappings.
              </p>

              <div className="sample-features-list">
                <div className="feature-item">
                  <CheckCircle2 size={14} className="feature-dot" />
                  <span>163 Pre-indexed Knowledge Chunks</span>
                </div>
                <div className="feature-item">
                  <CheckCircle2 size={14} className="feature-dot" />
                  <span>Core & Elective Prerequisites</span>
                </div>
                <div className="feature-item">
                  <CheckCircle2 size={14} className="feature-dot" />
                  <span>Career Specialization Pathways</span>
                </div>
              </div>

              <button
                type="button"
                className="sample-launch-btn"
                onClick={() => onLaunch({ filename: 'JAGSoM PGDM 2025-27', isDefault: true })}
              >
                <span>Launch with JAGSoM Catalogue</span>
                <ArrowRight size={16} />
              </button>
            </div>
          </motion.div>
        </div>

        {/* Feature Cards Grid */}
        <motion.div
          className="features-row"
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.5, delay: 0.3 }}
        >
          <div className="feature-card">
            <div className="feat-icon"><Compass size={18} /></div>
            <h4>Career Path Alignment</h4>
            <p>Ask which electives build skills for Credit Risk, NLP, Brand Strategy, or Quant Analytics.</p>
          </div>
          <div className="feature-card">
            <div className="feat-icon"><ShieldCheck size={18} /></div>
            <h4>Grounded with Citations</h4>
            <p>Every response references the exact catalogue page number with similarity match percentages.</p>
          </div>
          <div className="feature-card">
            <div className="feat-icon"><Sparkles size={18} /></div>
            <h4>Agentic Self-Correction</h4>
            <p>Routes questions, grades context relevance, and refines search queries automatically.</p>
          </div>
        </motion.div>
      </main>

      {/* Footer */}
      <footer className="landing-footer">
        <span>KYC — Know Your Courses • Powered by Agentic RAG & Groq</span>
      </footer>
    </div>
  );
}
