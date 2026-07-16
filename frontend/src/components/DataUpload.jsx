import { useState, useEffect } from 'react';
import { Upload, X, CheckCircle, AlertCircle, FileText, Trash2 } from 'lucide-react';

const SUPPORTED_CHANNELS = ['google', 'bing', 'meta']

// Filename must start with google, bing, or meta — anything after is fine
const detectChannel = (filename) => {
  const stem = filename.replace(/\.csv$/i, '').toLowerCase()
  return SUPPORTED_CHANNELS.find(ch => stem.startsWith(ch)) || null
}

const DataUpload = ({ onDataUploaded }) => {
  const [files, setFiles] = useState([]);           // [{ file, channel, valid }]
  const [uploading, setUploading] = useState(false);
  const [uploadResult, setUploadResult] = useState(null);
  const [dataStatus, setDataStatus] = useState(null);
  const [showUploadModal, setShowUploadModal] = useState(false);

  useEffect(() => {
    fetchDataStatus();
  }, []);

  const fetchDataStatus = async () => {
    try {
      const response = await fetch('http://localhost:8000/api/data-status');
      const data = await response.json();
      setDataStatus(data);
    } catch (error) {
      console.error('Failed to fetch data status:', error);
    }
  };

  const handleFileChange = (e) => {
    const selectedFiles = Array.from(e.target.files);
    const csvFiles = selectedFiles.filter(f => f.name.toLowerCase().endsWith('.csv'));
    if (csvFiles.length !== selectedFiles.length) {
      alert('Only CSV files are accepted');
    }
    setFiles(prev => {
      // Merge new picks with existing — last pick wins if same filename
      const incoming = csvFiles.map(f => ({ file: f, channel: detectChannel(f.name) }));
      const dedupedPrev = prev.filter(f => !incoming.some(n => n.file.name === f.file.name));
      return [...dedupedPrev, ...incoming];
    });
    setUploadResult(null);
    // Reset input so the same file can be re-picked if needed
    e.target.value = '';
  };

  const handleUpload = async () => {
    if (files.length === 0) {
      alert('Please select files to upload');
      return;
    }

    const unrecognised = files.filter(f => !f.channel);
    if (unrecognised.length > 0) {
      setUploadResult({
        success: false,
        message: `Cannot upload — channel name not found in filename(s): ${unrecognised.map(f => f.file.name).join(', ')}. Rename the file so it starts with the channel name (e.g. google_ads.csv).`,
        errors: []
      });
      return;
    }

    setUploading(true);
    setUploadResult(null);

    const formData = new FormData();
    files.forEach(({ file }) => {
      formData.append('files', file);
    });

    try {
      const response = await fetch('http://localhost:8000/api/upload-data', {
        method: 'POST',
        body: formData,
      });

      const result = await response.json();

      if (result.success) {
        setUploadResult({
          success: true,
          message: result.message,
          channels: result.channels,
          totalRecords: result.total_records,
          dateRange: result.date_range
        });

        // Refresh data status badge immediately
        await fetchDataStatus();

        // Notify parent component (refreshes available channels)
        if (onDataUploaded) {
          onDataUploaded(result);
        }

        setFiles([]);
        setTimeout(() => {
          setShowUploadModal(false);
          setUploadResult(null);
        }, 500);
      } else {
        setUploadResult({
          success: false,
          message: result.message || 'Upload failed',
          errors: result.files_failed || []
        });
      }
    } catch (error) {
      console.error('Upload error:', error);
      setUploadResult({
        success: false,
        message: 'Upload failed: ' + error.message
      });
    } finally {
      setUploading(false);
    }
  };

  const handleClearData = async () => {
    if (!confirm('Clear all uploaded data and return to default data?')) {
      return;
    }

    try {
      const response = await fetch('http://localhost:8000/api/upload-data', {
        method: 'DELETE',
      });

      const result = await response.json();

      if (result.success) {
        setUploadResult({
          success: true,
          message: 'Cleared uploaded data, using default data'
        });

        // Notify parent
        if (onDataUploaded) {
          onDataUploaded(result);
        }

        await fetchDataStatus();
      }
    } catch (error) {
      console.error('Clear error:', error);
      alert('Failed to clear data');
    }
  };

  const removeFile = (index) => {
    setFiles(prev => prev.filter((_, i) => i !== index));
  };

  return (
    <div className="space-y-4">
      {/* Data Status Badge */}
      {dataStatus && (
        <div className="flex items-center justify-between glass-effect p-4 rounded-xl border border-gray-700/50">
          <div className="flex items-center gap-3">
            <FileText className="w-5 h-5 text-trading-cyan" />
            <div>
              <div className="text-sm font-medium text-white">
                {dataStatus.using_uploaded_data ? 'Using Uploaded Data' : 'Using Default Data'}
              </div>
              <div className="text-xs text-gray-400">
                {dataStatus.total_records?.toLocaleString()} records
                {dataStatus.metadata?.channels && ` • ${dataStatus.metadata.channels.length} channels`}
              </div>
            </div>
          </div>
          <div className="flex gap-2">
            {dataStatus.using_uploaded_data && (
              <button
                onClick={handleClearData}
                className="flex items-center gap-1 px-3 py-1.5 text-sm text-red-400 hover:bg-red-500/10 rounded-lg transition-colors"
              >
                <Trash2 className="w-4 h-4" />
                Clear
              </button>
            )}
            <button
              onClick={() => setShowUploadModal(true)}
              className="flex items-center gap-2 px-4 py-2 bg-gradient-to-r from-trading-blue to-trading-cyan text-white text-sm rounded-xl hover:scale-105 transition-transform glow-blue font-medium"
            >
              <Upload className="w-4 h-4" />
              Upload Data
            </button>
          </div>
        </div>
      )}

      {/* Upload Modal */}
      {showUploadModal && (
        <div className="fixed inset-0 bg-black/80 backdrop-blur-sm flex items-center justify-center z-50 p-4">
          <div className="bg-trading-dark rounded-2xl shadow-2xl max-w-2xl w-full max-h-[90vh] overflow-y-auto border border-gray-700">
            {/* Header */}
            <div className="flex items-center justify-between p-6 border-b border-gray-700/50">
              <div>
                <h2 className="text-2xl font-bold text-white">Upload Custom Data</h2>
                <p className="text-sm text-gray-400 mt-1">Upload multiple CSV files (Google, Meta, Bing)</p>
              </div>
              <button
                onClick={() => setShowUploadModal(false)}
                className="p-2 hover:bg-white/10 rounded-lg transition-colors"
              >
                <X className="w-5 h-5 text-gray-400 hover:text-white" />
              </button>
            </div>

            {/* Content */}
            <div className="p-6 space-y-6">
              {/* File Input */}
              <div>
                <label className="block text-sm font-medium text-gray-300 mb-2">
                  Select CSV Files (Multiple files supported)
                </label>
                <div className="border-2 border-dashed border-gray-600 rounded-xl p-8 text-center hover:border-trading-cyan transition-all glass-effect">
                  <input
                    type="file"
                    multiple
                    accept=".csv"
                    onChange={handleFileChange}
                    className="hidden"
                    id="file-upload"
                  />
                  <label
                    htmlFor="file-upload"
                    className="cursor-pointer flex flex-col items-center"
                  >
                    <Upload className="w-12 h-12 text-trading-cyan mb-3" />
                    <span className="text-sm font-medium text-white">
                      Click to select CSV files
                    </span>
                    <span className="text-xs text-gray-400 mt-1">
                      Upload Google Ads, Meta Ads, and Bing Ads CSV files
                    </span>
                  </label>
                </div>
              </div>

              {/* Selected Files */}
              {files.length > 0 && (
                <div className="space-y-2">
                  <h3 className="text-sm font-medium text-gray-300">
                    Selected Files ({files.length})
                  </h3>
                  <div className="space-y-2">
                    {files.map(({ file, channel }, index) => (
                      <div
                        key={index}
                        className={`flex items-center justify-between p-3 glass-effect rounded-lg border ${
                          channel ? 'border-gray-700/50' : 'border-red-500/50 bg-red-500/5'
                        }`}
                      >
                        <div className="flex items-center gap-3">
                          <FileText className={`w-5 h-5 ${channel ? 'text-trading-cyan' : 'text-red-400'}`} />
                          <div>
                            <div className="text-sm font-medium text-white">{file.name}</div>
                            <div className="flex items-center gap-2 mt-0.5">
                              <span className="text-xs text-gray-400">{(file.size / 1024).toFixed(2)} KB</span>
                              {channel ? (
                                <span className="text-xs px-2 py-0.5 bg-trading-cyan/20 text-trading-cyan rounded-full uppercase font-medium">
                                  {channel}
                                </span>
                              ) : (
                                <span className="text-xs px-2 py-0.5 bg-red-500/20 text-red-400 rounded-full">
                                  channel not detected — rename file
                                </span>
                              )}
                            </div>
                          </div>
                        </div>
                        <button
                          onClick={() => removeFile(index)}
                          className="p-1 hover:bg-red-500/20 rounded transition-colors"
                        >
                          <X className="w-4 h-4 text-gray-400 hover:text-red-400" />
                        </button>
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {/* Upload Result */}
              {uploadResult && (
                <div className={`p-4 rounded-xl glass-effect border ${
                  uploadResult.success
                    ? 'bg-trading-green/10 border-trading-green/30'
                    : 'bg-red-500/10 border-red-500/30'
                }`}>
                  <div className="flex items-start gap-3">
                    {uploadResult.success ? (
                      <CheckCircle className="w-5 h-5 text-trading-green flex-shrink-0 mt-0.5" />
                    ) : (
                      <AlertCircle className="w-5 h-5 text-red-400 flex-shrink-0 mt-0.5" />
                    )}
                    <div className="flex-1">
                      <div className={`text-sm font-medium ${
                        uploadResult.success ? 'text-trading-green' : 'text-red-400'
                      }`}>
                        {uploadResult.message}
                      </div>
                      {uploadResult.success && uploadResult.channels && (
                        <div className="mt-2 text-xs text-gray-300 space-y-1">
                          <div>Channels: {uploadResult.channels.join(', ')}</div>
                          <div>Records: {uploadResult.totalRecords?.toLocaleString()}</div>
                          {uploadResult.dateRange && (
                            <div>
                              Date Range: {uploadResult.dateRange.start} to {uploadResult.dateRange.end}
                            </div>
                          )}
                        </div>
                      )}
                      {uploadResult.errors && uploadResult.errors.length > 0 && (
                        <div className="mt-2 text-xs text-red-300 space-y-1">
                          {uploadResult.errors.map((err, idx) => (
                            <div key={idx}>• {err.filename}: {err.error}</div>
                          ))}
                        </div>
                      )}
                    </div>
                  </div>
                </div>
              )}

              {/* Instructions */}
              <div className="glass-effect p-4 rounded-xl border border-trading-cyan/20 bg-trading-cyan/5">
                <h4 className="text-sm font-medium text-trading-cyan mb-2">File Naming — Required</h4>
                <p className="text-xs text-gray-400 mb-2">
                  Filename must <strong className="text-white">start with google, bing, or meta</strong> — anything after is fine. This tells the system which channel the file belongs to and ensures re-uploads replace the correct dataset.
                </p>
                <div className="grid grid-cols-3 gap-2 mb-3">
                  {[
                    { label: 'Google', examples: 'google_ads.csv' },
                    { label: 'Meta', examples: 'meta_ads.csv' },
                    { label: 'Bing', examples: 'bing_ads.csv' },
                  ].map(({ label, examples }) => (
                    <div key={label} className="bg-trading-darker rounded-lg p-2 text-center">
                      <div className="text-xs font-semibold text-white mb-1">{label}</div>
                      <div className="text-xs text-trading-cyan font-mono">{examples}</div>
                    </div>
                  ))}
                </div>
                <h4 className="text-sm font-medium text-trading-cyan mb-1 mt-3">Required CSV Columns</h4>
                <ul className="text-xs text-gray-300 space-y-1">
                  <li>• <strong className="text-white">date</strong> column (any standard date format)</li>
                  <li>• <strong className="text-white">revenue</strong> column (numeric, in dollars)</li>
                  <li>• Optional: <strong className="text-white">spend</strong>, <strong className="text-white">clicks</strong>, <strong className="text-white">impressions</strong></li>
                </ul>
              </div>
            </div>

            {/* Footer */}
            <div className="flex items-center justify-end gap-3 p-6 border-t border-gray-700/50">
              <button
                onClick={() => setShowUploadModal(false)}
                className="px-4 py-2 text-gray-300 hover:bg-white/10 rounded-lg transition-colors"
              >
                Cancel
              </button>
              <button
                onClick={handleUpload}
                disabled={files.length === 0 || uploading || files.some(f => !f.channel)}
                className={`flex items-center gap-2 px-6 py-2 rounded-xl font-medium transition-all ${
                  files.length === 0 || uploading || files.some(f => !f.channel)
                    ? 'bg-gray-700 text-gray-500 cursor-not-allowed'
                    : 'bg-gradient-to-r from-trading-blue to-trading-cyan text-white hover:scale-105 glow-blue'
                }`}
              >
                {uploading ? (
                  <>
                    <div className="w-4 h-4 border-2 border-white border-t-transparent rounded-full animate-spin" />
                    Uploading...
                  </>
                ) : (
                  <>
                    <Upload className="w-4 h-4" />
                    Upload Files
                  </>
                )}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

export default DataUpload;
