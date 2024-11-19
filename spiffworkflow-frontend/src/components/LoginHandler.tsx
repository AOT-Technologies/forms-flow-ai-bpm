import { useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import UserService from '../services/UserService';
import { BASENAME_URL } from '../config';

export default function LoginHandler() {
  const navigate = useNavigate();
  useEffect(() => {
    if (!UserService.isLoggedIn()) {
      navigate(BASENAME_URL+ `/login?original_url=${UserService.getCurrentLocation()}`);
    }
  }, [navigate]);
  return null;
}
