import axios from 'axios';

const RAG_URL = import.meta.env.VITE_RAG_URL || 'http://localhost:8001';

const ragApi = axios.create({
  baseURL: RAG_URL,
  headers: {
    'Content-Type': 'application/json',
  },
});

export default ragApi;
